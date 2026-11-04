# P1 packaged-interpreter qualification driver for a fresh GitHub-hosted Windows runner (inc 633).
#
# Runs every stage once, in order, and writes one machine-readable receipt. It never retries a failed stage and never
# relaxes a criterion. Stages:
#   resources -> commit -> download -> archive -> manifest -> extract -> tree -> signature -> runtime_id -> identity
#   -> provision (network allowed) -> boundary (outbound block on the exact python.exe + controls)
#   -> verify -> arctic -> deberta (all offline, serial, one model per process) -> after (integrity) -> cleanup
# Verdict: a failed integrity/contract/scientific/isolation check is FAIL; otherwise a failed infrastructure check or a
# stage that did not complete is INCONCLUSIVE; PASS needs every stage complete and every check passed.
# Exit code: 0 PASS, 1 FAIL, 2 INCONCLUSIVE.
param(
    [Parameter(Mandatory)][string]$Repo,
    [Parameter(Mandatory)][string]$Work
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false   # native exit codes are read explicitly
Set-StrictMode -Version 3

# --- pinned identities (committed; any drift is a FAIL, never a re-pin) ---------------------------------------------
$BaseCommit = 'd6649dfbd19c9160b5a002a799be81c397f30dda'
$RegressionPassCommit = 'c7c645fe17a861f2a5b876596a21629b311c2c8c'
$RuntimeId = 'win-x86_64-py3.11-s1-2094b5a287a1dd54'
$ArchiveSha = 'ce0d2052a0a9dc1cc542aa9ebcbe32b938984f6ed948e5b8659de2c011334d4c'
$ArchiveBytes = 382931495
$TreeSha = 'a51f65b35c9d5abbdf3317569f5ee798bcb20fd6437459913b3fcf030167f2fc'
$EntryCount = 41338
$UnpackedBytes = 1315019532
$PythonVersion = '3.11.15'
$ReleaseBase = "https://github.com/cliffworkman/callosum/releases/download/python-runtime-$RuntimeId"
# Inc 634 adds the two files of the Arctic pooling compatibility fix found by run 41861114677, named exactly.
$AllowedChanges = @('^tools/qualification/p1/', '^\.github/workflows/p1-qualification\.yml$', '^app/backend/embeddings/models\.py$', '^tests/test_embedding_profiles\.py$')
$FirewallGroup = 'callosum-p1-qualification'
# Start gate, from the workload rather than the laptop: the predeclared P1b ceiling is 2.87 GB peak commit for the
# heavier (DeBERTa) process and the models run one at a time, so 8 GiB free commit and 6 GiB available physical memory
# leave more than 2x headroom. A model process is stopped (INCONCLUSIVE) if available physical memory falls below 1.5 GiB.
$GatePhysGiB = 6; $GateCommitGiB = 8; $GateDiskGiB = 6; $FloorPhysGiB = 1.5
$Stages = 'resources', 'commit', 'download', 'archive', 'manifest', 'extract', 'tree', 'signature', 'runtime_id',
'identity', 'provision', 'boundary', 'verify', 'arctic', 'deberta', 'after', 'cleanup'

$Here = $PSScriptRoot
$Fixture = Join-Path $Here 'fixtures\p1-probe-v1.json'
$Probe = Join-Path $Here 'p1_probe.py'
New-Item -ItemType Directory -Path $Work -ErrorAction SilentlyContinue | Out-Null
if (Get-ChildItem -LiteralPath $Work -Force | Select-Object -First 1) { throw "work directory is not empty: $Work" }
$Work = (Resolve-Path -LiteralPath $Work).Path
$Dl = Join-Path $Work 'download'; $Runtime = Join-Path $Work 'runtime'; $Out = Join-Path $Work 'out'
$State = Join-Path $Work 'state'; $Hf = Join-Path $Work 'hf'; $Tmp = Join-Path $Work 'tmp'; $Cwd = Join-Path $Work 'cwd'
foreach ($d in $Dl, $Out, $State, $Hf, $Tmp, $Cwd, (Join-Path $Work 'settings')) { New-Item -ItemType Directory -Path $d | Out-Null }
$Python = Join-Path $Runtime 'python.exe'

$Checks = [System.Collections.Generic.List[object]]::new()
$Completed = [System.Collections.Generic.List[string]]::new()
$Info = [ordered]@{}
$Processes = [ordered]@{}
$script:FirewallTouched = $false
$script:ProfilesBefore = @()

function Log([string]$m) { $line = "$(Get-Date -Format o) $m"; Write-Host $line; Add-Content -LiteralPath (Join-Path $Out 'driver.log') -Value $line }
function Add-Check([string]$Stage, [string]$Id, [string]$Kind, [bool]$Ok, $Detail = '') {
    $Checks.Add([ordered]@{ stage = $Stage; id = $Id; kind = $Kind; ok = $Ok; detail = $Detail })
    Log ("{0} {1}/{2} [{3}] {4}" -f ($(if ($Ok) { 'PASS' } else { 'FAIL' })), $Stage, $Id, $Kind, ($Detail | ConvertTo-Json -Compress -Depth 6))
    return $Ok
}
function Stage-Ok([string]$Stage) { -not ($Checks | Where-Object { $_.stage -eq $Stage -and -not $_.ok }) }
function Complete([string]$Stage) { $ok = Stage-Ok $Stage; if ($ok) { $Completed.Add($Stage) }; return $ok }
function Rename-Stage([string]$From, [string]$To) { foreach ($c in @($Checks | Where-Object { $_.stage -eq $From })) { $c.stage = $To } }
function Field($Object, [string]$Name) { $p = $Object.PSObject.Properties[$Name]; if ($p) { $p.Value } else { $null } }
function Sha256([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }
function Memory { $os = Get-CimInstance Win32_OperatingSystem; [ordered]@{ phys_gib = [math]::Round($os.FreePhysicalMemory / 1MB, 2); commit_gib = [math]::Round($os.FreeVirtualMemory / 1MB, 2) } }
function Tree-Digest {
    $o = & pwsh -NoProfile -File (Join-Path $Here 'p1_tree_digest.ps1') -Root $Runtime 2>&1 | Out-String
    if ($o -match 'entries (\d+) bytes (\d+) digest ([0-9a-f]{64})') { return [ordered]@{ entries = [int64]$Matches[1]; bytes = [int64]$Matches[2]; digest = $Matches[3] } }
    return [ordered]@{ error = $o.Trim() }
}

function Invoke-Phase([string]$Stage, [string]$Phase, [bool]$Offline, [int]$TimeoutSec, [string[]]$Extra = @()) {
    $outFile = Join-Path $Out "$Stage.json"
    $psi = [System.Diagnostics.ProcessStartInfo]::new($Python)
    foreach ($a in @('-I', '-B', $Probe, $Phase, '--repo', $Repo, '--work', $Work, '--state', $State, '--out', $outFile,
            '--fixture', $Fixture, '--manifest', (Join-Path $Dl 'runtime-manifest.json'), '--expected-python', $Python,
            '--python-version', $PythonVersion) + $Extra) { $psi.ArgumentList.Add($a) }
    $psi.UseShellExecute = $false; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    $psi.WorkingDirectory = $Cwd
    foreach ($k in @($psi.Environment.Keys)) {
        if ($k -match '^(HF_|HUGGING|TRANSFORMERS_|CALLOSUM_|PYTHON|ACTIONS_|GITHUB_TOKEN)') { [void]$psi.Environment.Remove($k) }
    }
    $envs = @{ HF_HOME = $Hf; HF_HUB_DISABLE_TELEMETRY = '1'; HF_HUB_DISABLE_SYMLINKS_WARNING = '1'; HF_HUB_DISABLE_PROGRESS_BARS = '1'
        CALLOSUM_MODEL_PROVISIONING_DIR = $State; CALLOSUM_DISABLE_MODEL_PROVISIONING = '1'
        CALLOSUM_SETTINGS_PATH = (Join-Path $Work 'settings\app-settings.json'); TEMP = $Tmp; TMP = $Tmp; TOKENIZERS_PARALLELISM = 'false'
    }
    if ($Offline) { $envs.HF_HUB_OFFLINE = '1'; $envs.TRANSFORMERS_OFFLINE = '1' }
    foreach ($k in $envs.Keys) { $psi.Environment[$k] = $envs[$k] }
    Log "start $Stage ($Phase, offline=$Offline)"
    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEndAsync(); $stderr = $p.StandardError.ReadToEndAsync()
    $peakWs = 0; $peakPriv = 0; $minPhys = [double]::MaxValue; $minCommit = [double]::MaxValue; $children = @{}; $stopped = $null
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while (-not $p.WaitForExit(1000)) {
        try { $p.Refresh(); $peakWs = [math]::Max($peakWs, $p.WorkingSet64); $peakPriv = [math]::Max($peakPriv, $p.PrivateMemorySize64) } catch { }
        $m = Memory; $minPhys = [math]::Min($minPhys, $m.phys_gib); $minCommit = [math]::Min($minCommit, $m.commit_gib)
        $all = @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, Name, ExecutablePath)
        $front = @($p.Id)
        while ($front.Count) {
            $next = @(); foreach ($c in $all) { if ($front -contains $c.ParentProcessId -and -not $children.ContainsKey([string]$c.ProcessId)) { $children[[string]$c.ProcessId] = "$($c.Name) $($c.ExecutablePath)"; $next += $c.ProcessId } }
            $front = $next
        }
        if ($m.phys_gib -lt $FloorPhysGiB) { $stopped = "available physical memory $($m.phys_gib) GiB below the $FloorPhysGiB GiB floor" }
        elseif ($sw.Elapsed.TotalSeconds -gt $TimeoutSec) { $stopped = "timeout after $TimeoutSec s" }
        if ($stopped) { Log "stopping $Stage : $stopped"; $p.Kill($true); $p.WaitForExit(); break }
    }
    $p.WaitForExit()
    Set-Content -LiteralPath (Join-Path $Out "$Stage.stdout.txt") -Value $stdout.Result
    Set-Content -LiteralPath (Join-Path $Out "$Stage.stderr.txt") -Value $stderr.Result
    $unexpected = @($children.Values | Where-Object { $_ -notmatch '^conhost\.exe ' })
    $Processes[$Stage] = [ordered]@{ exit_code = $p.ExitCode; seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
        sampled_peak_working_set_mib = [math]::Round($peakWs / 1MB, 1); sampled_peak_private_mib = [math]::Round($peakPriv / 1MB, 1)
        min_available_phys_gib = $minPhys; min_free_commit_gib = $minCommit; child_processes = @($children.Values); stopped = $stopped
    }
    [void](Add-Check $Stage 'no_unexpected_child_process' 'isolation' ($unexpected.Count -eq 0) @($children.Values))
    if ($stopped) { [void](Add-Check $Stage 'process_not_stopped' 'infrastructure' $false $stopped); return $null }
    if (-not (Test-Path -LiteralPath $outFile)) { [void](Add-Check $Stage 'phase_result_written' 'integrity' $false "exit $($p.ExitCode) without a result file"); return $null }
    $result = Get-Content -Raw -LiteralPath $outFile | ConvertFrom-Json -AsHashtable
    $reported = if ($result.ContainsKey('checks')) { @($result['checks']) } else { @() }
    if ($reported.Count -eq 0) { [void](Add-Check $Stage 'phase_reported_checks' 'integrity' $false 'no checks reported') }
    foreach ($c in $reported) { [void](Add-Check $Stage $c['id'] $c['kind'] ([bool]$c['ok']) $c['detail']) }
    return $result
}
function Phase-Stage([string]$Stage, [string]$Phase, [bool]$Offline, [int]$TimeoutSec) {
    [void](Invoke-Phase $Stage $Phase $Offline $TimeoutSec)
    return (Complete $Stage)
}

function Remove-Firewall {
    if (-not $script:FirewallTouched) { return }
    Get-NetFirewallRule -Group $FirewallGroup -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    foreach ($pr in $script:ProfilesBefore) { Set-NetFirewallProfile -Name $pr.Name -Enabled $pr.Enabled }
    $left = @(Get-NetFirewallRule -Group $FirewallGroup -ErrorAction SilentlyContinue).Count
    [void](Add-Check 'cleanup' 'firewall_rules_removed' 'infrastructure' ($left -eq 0) "$left rules left")
    $script:FirewallTouched = $false
}

function Run-Stages {
    # resources
    $os = Get-CimInstance Win32_OperatingSystem
    $disk = (Get-PSDrive -Name ((Split-Path -Qualifier $Work).TrimEnd(':'))).Free / 1GB
    $m = Memory
    $Info.resources = [ordered]@{ total_phys_gib = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2); commit_limit_gib = [math]::Round($os.TotalVirtualMemorySize / 1MB, 2)
        available_phys_gib = $m.phys_gib; free_commit_gib = $m.commit_gib; free_disk_gib = [math]::Round($disk, 2); work_drive = (Split-Path -Qualifier $Work)
        logical_processors = (Get-CimInstance Win32_Processor | Measure-Object NumberOfLogicalProcessors -Sum).Sum
        cpu = @(Get-CimInstance Win32_Processor | ForEach-Object Name); os = $os.Caption; os_build = $os.BuildNumber
        image_os = $env:ImageOS; image_version = $env:ImageVersion; gate = @{ phys_gib = $GatePhysGiB; commit_gib = $GateCommitGiB; disk_gib = $GateDiskGiB }
    }
    $admin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    [void](Add-Check 'resources' 'available_physical_memory' 'infrastructure' ($m.phys_gib -ge $GatePhysGiB) $m.phys_gib)
    [void](Add-Check 'resources' 'free_commit' 'infrastructure' ($m.commit_gib -ge $GateCommitGiB) $m.commit_gib)
    [void](Add-Check 'resources' 'free_disk' 'infrastructure' ($disk -ge $GateDiskGiB) ([math]::Round($disk, 2)))
    [void](Add-Check 'resources' 'administrator_for_firewall' 'infrastructure' $admin '')
    if (-not (Complete 'resources')) { return }

    # commit: the application tree is byte-for-byte the qualification base; only this harness was added
    $head = (git -C $Repo rev-parse HEAD).Trim()
    $Info.commit = [ordered]@{ head = $head; base = $BaseCommit; regression_pass = $RegressionPassCommit; github_sha = $env:GITHUB_SHA; ref = $env:GITHUB_REF }
    [void](Add-Check 'commit' 'head_is_triggering_commit' 'integrity' ((-not $env:GITHUB_SHA) -or $head -eq $env:GITHUB_SHA) $head)
    git -C $Repo merge-base --is-ancestor $BaseCommit $head; $anc = $LASTEXITCODE -eq 0
    [void](Add-Check 'commit' 'base_is_ancestor' 'integrity' $anc $BaseCommit)
    git -C $Repo merge-base --is-ancestor $RegressionPassCommit $BaseCommit; [void](Add-Check 'commit' 'regression_pass_is_ancestor' 'integrity' ($LASTEXITCODE -eq 0) $RegressionPassCommit)
    $changed = @(git -C $Repo diff --name-only $BaseCommit $head)
    $foreign = @($changed | Where-Object { $f = $_; -not ($AllowedChanges | Where-Object { $f -match $_ }) })
    $Info.commit.changed_files = $changed
    [void](Add-Check 'commit' 'only_qualification_files_changed' 'integrity' ($anc -and $foreign.Count -eq 0) $foreign)
    $dirty = @(git -C $Repo status --porcelain)
    [void](Add-Check 'commit' 'clean_checkout' 'integrity' ($dirty.Count -eq 0) $dirty)
    $script:PycacheBefore = @(Get-ChildItem -LiteralPath (Join-Path $Repo 'app') -Recurse -Directory -Filter '__pycache__' -Force).Count
    if (-not (Complete 'commit')) { return }

    # download (the only network use outside model provisioning)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        foreach ($name in "$RuntimeId.tar.gz", 'runtime-manifest.json', 'runtime-manifest.json.sig') {
            Invoke-WebRequest -Uri "$ReleaseBase/$name" -OutFile (Join-Path $Dl $name) -MaximumRetryCount 3 -RetryIntervalSec 15 -UseBasicParsing
        }
        [void](Add-Check 'download' 'runtime_release_downloaded' 'infrastructure' $true "$([math]::Round($sw.Elapsed.TotalSeconds,1)) s")
    } catch { [void](Add-Check 'download' 'runtime_release_downloaded' 'infrastructure' $false $_.Exception.Message) }
    if (-not (Complete 'download')) { return }

    # archive
    $archive = Join-Path $Dl "$RuntimeId.tar.gz"
    $size = (Get-Item -LiteralPath $archive).Length; $sha = Sha256 $archive
    $Info.runtime = [ordered]@{ id = $RuntimeId; archive_url = "$ReleaseBase/$RuntimeId.tar.gz"; archive_bytes = $size; archive_sha256 = $sha }
    [void](Add-Check 'archive' 'archive_bytes' 'integrity' ($size -eq $ArchiveBytes) $size)
    [void](Add-Check 'archive' 'archive_sha256' 'integrity' ($sha -ceq $ArchiveSha) $sha)
    if (-not (Complete 'archive')) { return }

    # manifest (fields must equal the pinned identity before anything is extracted)
    $mf = Get-Content -Raw -LiteralPath (Join-Path $Dl 'runtime-manifest.json') | ConvertFrom-Json
    $Info.runtime.manifest_sha256 = Sha256 (Join-Path $Dl 'runtime-manifest.json')
    foreach ($pair in @(@('runtime_id', $RuntimeId), @('archive_sha256', $ArchiveSha), @('archive_bytes', $ArchiveBytes), @('tree_sha256', $TreeSha),
            @('entry_count', $EntryCount), @('unpacked_bytes', $UnpackedBytes), @('python_relative_path', 'python.exe'), @('python_version', $PythonVersion))) {
        $value = Field $mf $pair[0]
        [void](Add-Check 'manifest' "manifest_$($pair[0])" 'integrity' ($null -ne $value -and "$value" -ceq "$($pair[1])") $value)
    }
    if (-not (Complete 'manifest')) { return }

    # extract with the installer's rules; nothing extracted runs before the tree digest matches
    $x = & pwsh -NoProfile -File (Join-Path $Here 'p1_extract_runtime.ps1') -Archive $archive -Dest $Runtime -ManifestPath (Join-Path $Dl 'runtime-manifest.json') -ListOut (Join-Path $Out 'extracted-entries.txt') 2>&1 | Out-String
    $xc = $LASTEXITCODE; Set-Content -LiteralPath (Join-Path $Out 'extract.log') -Value $x
    [void](Add-Check 'extract' 'safe_extraction_stream_digest' 'integrity' ($xc -eq 0 -and $x -match 'EXTRACT-STREAM TREE MATCH') ($x.Trim() -split "`n" | Select-Object -Last 2))
    if (-not (Complete 'extract')) { return }

    # tree: an independent re-read of the extracted files
    $t = Tree-Digest; $Info.runtime.tree_before = $t
    [void](Add-Check 'tree' 'runtime_tree_sha256' 'integrity' ($t.Contains('digest') -and $t.digest -ceq $TreeSha -and $t.entries -eq $EntryCount -and $t.bytes -eq $UnpackedBytes) $t)
    if (-not (Complete 'tree')) { return }

    # signature: the manifest is signed by the key the desktop shell trusts
    $s = & $Python -I -B (Join-Path $Here 'p1_minisign.py') (Join-Path $Dl 'runtime-manifest.json') (Join-Path $Dl 'runtime-manifest.json.sig') (Join-Path $Repo 'app\desktop-shell\src-tauri\src\python_runtime.rs') 2>&1 | Out-String
    [void](Add-Check 'signature' 'manifest_signature' 'integrity' ($LASTEXITCODE -eq 0 -and $s -match 'SIGNATURE OK') $s.Trim())
    if (-not (Complete 'signature')) { return }

    # runtime_id: the committed runtime inputs still name this runtime
    $rid = (& $Python -I -B (Join-Path $Repo 'app\desktop-shell\packaging\package_python_runtime.py') id --platform windows-x86_64 2>&1 | Out-String).Trim()
    [void](Add-Check 'runtime_id' 'committed_inputs_name_runtime' 'integrity' ($rid -ceq $RuntimeId) $rid)
    if (-not (Complete 'runtime_id')) { return }

    if (-not (Phase-Stage 'identity' 'identity' $false 300)) { return }
    if (-not (Phase-Stage 'provision' 'provision' $false 2400)) { return }

    # boundary: block the exact interpreter image, then prove the block with negative and positive controls
    $script:ProfilesBefore = @(Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultOutboundAction)
    $Info.firewall_profiles_before = $script:ProfilesBefore
    $script:FirewallTouched = $true
    Set-NetFirewallProfile -Profile Domain, Private, Public -Enabled True
    New-NetFirewallRule -Name "callosum-p1-$($env:GITHUB_RUN_ID)-$($env:GITHUB_RUN_ATTEMPT)" -DisplayName 'callosum P1 offline boundary' -Group $FirewallGroup `
        -Direction Outbound -Action Block -Program $Python -Profile Any -Enabled True | Out-Null
    $filters = @(Get-NetFirewallRule -Group $FirewallGroup | Get-NetFirewallApplicationFilter | ForEach-Object Program)
    [void](Add-Check 'boundary' 'rule_targets_exact_interpreter' 'infrastructure' ($filters.Count -eq 1 -and $filters[0] -eq $Python) $filters)
    $profilesOff = @(Get-NetFirewallProfile | Where-Object { "$($_.Enabled)" -ne 'True' } | ForEach-Object Name)
    [void](Add-Check 'boundary' 'firewall_profiles_enabled' 'infrastructure' ($profilesOff.Count -eq 0) $profilesOff)
    $ip = @([System.Net.Dns]::GetHostAddresses('huggingface.co') | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | ForEach-Object IPAddressToString) | Select-Object -First 1
    if (-not (Add-Check 'boundary' 'control_target_resolved' 'infrastructure' ([bool]$ip) $ip)) { [void](Complete 'boundary'); return }
    $positive = $false
    try { $tcp = [System.Net.Sockets.TcpClient]::new(); $positive = $tcp.ConnectAsync($ip, 443).Wait(10000) -and $tcp.Connected; $tcp.Dispose() } catch { $positive = $false }
    [void](Add-Check 'boundary' 'positive_control_other_process_connects' 'infrastructure' $positive "pwsh -> ${ip}:443")
    [void](Invoke-Phase 'netcheck' 'netcheck' $true 300 @('--target-ip', $ip, '--target-hosts', 'huggingface.co', 'github.com'))
    Rename-Stage 'netcheck' 'boundary'
    $Info.boundary = [ordered]@{ mechanism = 'Windows Firewall outbound block rule on the exact interpreter path'; target_ip = $ip }
    if (-not (Complete 'boundary')) { return }   # never claim offline results without a demonstrated block

    if (-not (Phase-Stage 'verify' 'verify' $true 900)) { return }
    [void](Phase-Stage 'arctic' 'arctic' $true 900)     # serial; a failure in one model still records the other
    [void](Phase-Stage 'deberta' 'deberta' $true 900)

    # after: nothing the probes ran may have changed the runtime, the checkpoints or the checkout
    $t2 = Tree-Digest; $Info.runtime.tree_after = $t2
    [void](Add-Check 'after' 'runtime_tree_unchanged' 'integrity' ($t2.Contains('digest') -and $t2.digest -ceq $TreeSha) $t2)
    [void](Invoke-Phase 'verify_after' 'verify' $true 900)
    Rename-Stage 'verify_after' 'after'
    $pyc = @(Get-ChildItem -LiteralPath (Join-Path $Repo 'app') -Recurse -Directory -Filter '__pycache__' -Force).Count
    [void](Add-Check 'after' 'no_bytecode_written_to_checkout' 'integrity' ($pyc -eq $script:PycacheBefore) "$script:PycacheBefore -> $pyc")
    $dirty = @(git -C $Repo status --porcelain)
    [void](Add-Check 'after' 'checkout_unchanged' 'integrity' ($dirty.Count -eq 0) $dirty)
    $survivors = @(Get-CimInstance Win32_Process -Property ProcessId, ExecutablePath | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($Runtime, [StringComparison]::OrdinalIgnoreCase) })
    [void](Add-Check 'after' 'no_surviving_runtime_process' 'integrity' ($survivors.Count -eq 0) @($survivors | ForEach-Object ProcessId))
    [void](Complete 'after')
}

$started = Get-Date
try { Run-Stages }
catch { [void](Add-Check 'driver' 'driver_exception' 'infrastructure' $false "$($_.Exception.Message) at $($_.InvocationInfo.PositionMessage)") }
finally {
    try { Remove-Firewall } catch { [void](Add-Check 'cleanup' 'firewall_cleanup_exception' 'infrastructure' $false $_.Exception.Message) }
    if (-not ($Checks | Where-Object { $_.stage -eq 'cleanup' -and -not $_.ok })) { $Completed.Add('cleanup') }
}

$failed = @($Checks | Where-Object { -not $_.ok })
$hard = @($failed | Where-Object { $_.kind -ne 'infrastructure' })
$missing = @($Stages | Where-Object { $Completed -notcontains $_ })
$verdict = if ($hard.Count) { 'FAIL' } elseif ($failed.Count -or $missing.Count) { 'INCONCLUSIVE' } else { 'PASS' }
$receipt = [ordered]@{
    schema = 'callosum-p1-qualification-receipt-v1'; stage = 'P1 packaged-interpreter model compatibility (Windows x64)'
    verdict = $verdict; started = $started.ToString('o'); finished = (Get-Date).ToString('o')
    run = [ordered]@{ repository = $env:GITHUB_REPOSITORY; ref = $env:GITHUB_REF; sha = $env:GITHUB_SHA; run_id = $env:GITHUB_RUN_ID; attempt = $env:GITHUB_RUN_ATTEMPT; workflow = $env:GITHUB_WORKFLOW; runner = $env:RUNNER_NAME }
    fixture = [ordered]@{ path = 'tools/qualification/p1/fixtures/p1-probe-v1.json'; sha256 = (Sha256 $Fixture) }
    harness_sha256 = [ordered]@{ driver = (Sha256 $PSCommandPath); probe = (Sha256 $Probe); extract = (Sha256 (Join-Path $Here 'p1_extract_runtime.ps1')); tree = (Sha256 (Join-Path $Here 'p1_tree_digest.ps1')); minisign = (Sha256 (Join-Path $Here 'p1_minisign.py')) }
    info = $Info; processes = $Processes; stages_completed = $Completed; stages_missing = $missing
    failed_checks = $failed; checks = $Checks
    limitations = @(
        'The outbound block applies to the exact python.exe image only; a child process of another image would not be covered (none is expected; any is recorded and fails isolation).',
        'Name resolution is performed by the Windows DNS Client service, not the blocked process, so DNS queries can leave the VM; they carry only public host names.',
        'The block is demonstrated by connection attempts refused with WSAEACCES (10013) and a positive control from another process; absence of observed traffic is not used as evidence.',
        'Arctic and DeBERTa parity uses the public 3-text / 2-pair probe set frozen from the 2026-10-31 development reference; the private G1 Set A/B (99/209 pairs) categorical parity is P1b, not covered here.',
        'App-derived statuses are evaluated with the app status rule at fixed retrieval/quote confidences (1.0/1.0 and 0.0/0.0); MiniLM retrieval similarity is not exercised in P1.',
        'Memory figures are measured on a hosted VM and are evidence of P1 completion only; they are not the predeclared P1b latency/memory acceptance.'
    )
    not_covered = @('P1b DeBERTa latency and memory acceptance', 'P2 packaged-backend behaviour', 'P3 worker lifecycle and recovery', 'P4 installed Tauri application', 'macOS and Linux', 'Issue #110', 'independent security review', 'the 0.6.0 release gate')
}
$receipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $Out 'p1-receipt.json') -Encoding utf8NoBOM
$summary = @("## P1 qualification: $verdict", '', "Commit $($env:GITHUB_SHA), runtime $RuntimeId", '', "Stages completed: $($Completed -join ', ')", "Stages missing: $($missing -join ', ')", '', '| stage | check | kind | detail |', '|---|---|---|---|')
foreach ($f in $failed) {
    $d = (ConvertTo-Json -InputObject $f.detail -Compress -Depth 4) -replace '\|', '/'
    $summary += "| $($f.stage) | $($f.id) | $($f.kind) | $($d.Substring(0, [math]::Min(300, $d.Length))) |"
}
$summary | Set-Content -LiteralPath (Join-Path $Out 'p1-summary.md') -Encoding utf8NoBOM
if ($env:GITHUB_STEP_SUMMARY) { $summary | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY }
if ($env:GITHUB_OUTPUT) { "verdict=$verdict" | Add-Content -LiteralPath $env:GITHUB_OUTPUT }
Log "VERDICT $verdict ($($failed.Count) failed checks, missing stages: $($missing -join ','))"
exit $(switch ($verdict) { 'PASS' { 0 } 'FAIL' { 1 } default { 2 } })
