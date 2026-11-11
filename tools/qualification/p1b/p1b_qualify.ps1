# P1b hosted Windows qualification driver (inc 636; revision 2, inc 637): DeBERTa performance and resources on the
# packaged runtime, with the inc 637 float32 loading correction.
#
# Method: P1B_PREDECLARATION.md (v1, unchanged) as revised by P1B_PREDECLARATION_V2.md, both pinned below by SHA-256.
# Every stage runs once, in order; nothing is retried except the predeclared once-per-slot noise repeat. Stages:
#   resources -> commit -> download -> archive -> manifest -> extract -> tree -> signature -> runtime_id -> identity
#   -> provision (network allowed) -> boundary (outbound block on the exact python.exe + controls) -> verify -> tokenize
#   -> precision (float32 on the loaded model + P1 float32 parity; stops before any timing) -> seed -> failclosed -> warmup -> deberta_solo -> minilm2_solo -> worker_start -> deberta_concurrent
#   -> minilm2_concurrent -> worker_stop -> evaluate -> after -> cleanup
# Verdict: a failed integrity/contract/scientific/isolation/performance check is FAIL; otherwise a failed
# infrastructure check or an incomplete stage is INCONCLUSIVE; PASS needs every stage complete and every check passed.
# Exit code: 0 PASS, 1 FAIL, 2 INCONCLUSIVE.
param(
    [Parameter(Mandatory)][string]$Repo,
    [Parameter(Mandatory)][string]$Work
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
Set-StrictMode -Version 3

# --- pinned identities (committed; any drift is a FAIL, never a re-pin) ---------------------------------------------
$QualifiedP1Commit = 'f1d6c4302af3350146676fd79b7c62bacf3495c7'
$IntegrationHead = 'da47c81bcbd928da2d7a2ab7f596d0cecc7d54f9'   # integrations/alembic/pyproject/uv.lock trees equal this commit's; the two P1 pins equal the qualified P1 commit's
# app and tests are the inc 637 corrected source: the integration head's trees (app 39edfb6a, tests 2ab60bee) plus
# exactly the files in $AllowedChanges below (float32 DeBERTa loading and its tests). Nothing else differs.
$TreePins = [ordered]@{
    'app' = 'aabc1618d81a62054eaa8e9245dbf36a8c263e59'; 'integrations' = 'f02b9dbad694cceee0f109d454465922380e8fa9'
    'alembic' = '88d476b99486fe22716b6156437006d4cc31f525'; 'tests' = '6372b3ae068618cd171901c2a5063b8054ae3efd'
    'pyproject.toml' = '53edf2b51b86385154bac5ed1840512ca026caca'; 'uv.lock' = 'e5966c320bb5e4f113fd18c58de2ec8ef8e1f74b'
    'tools/qualification/p1' = 'bed59ea6e768bc6bd19349290b63b97e7204bcef'; '.github/workflows/p1-qualification.yml' = '5b328e8de4c9c268cf85278a0120e156760fc12b'
}
$PredeclarationSha = '6a5a2d85adce3c91d05a81ce506373d190c5e7474ecb9eb6873f75bc8d93e063'   # v1, the first attempt's; unchanged
$PredeclarationV2Sha = 'cd04c73ad591d8ef1af48dd4cca720103f64bd3e0e2eee40f7da6af13633d030'
$FixtureSha = 'acd2723c5b389f9f446ee00069475a6c256de3c19865108b3bd9f66aafb49920'
$CorpusSha = 'cb488cdea1277d3f4f9738f21f146cc3d0bda5bd00f6b70af9b1147203d416bc'
$RuntimeId = 'win-x86_64-py3.11-s1-2094b5a287a1dd54'
$ArchiveSha = 'ce0d2052a0a9dc1cc542aa9ebcbe32b938984f6ed948e5b8659de2c011334d4c'
$ArchiveBytes = 382931495
$TreeSha = 'a51f65b35c9d5abbdf3317569f5ee798bcb20fd6437459913b3fcf030167f2fc'
$EntryCount = 41338
$UnpackedBytes = 1315019532
$PythonVersion = '3.11.15'
$ReleaseBase = "https://github.com/cliffworkman/callosum/releases/download/python-runtime-$RuntimeId"
$AllowedChanges = @('^tools/qualification/p1b/', '^\.github/workflows/p1b-qualification\.yml$',
    '^app/backend/model_runtime\.py$', '^app/backend/summarization/verification\.py$', '^app/backend/summarization/stance\.py$',
    '^tests/test_nli_precision\.py$', '^tests/test_desktop_packaging\.py$')   # v2 §2: the inc 637 correction, exactly
$FirewallGroup = 'callosum-p1b-qualification'
$GatePhysGiB = 6; $GateCommitGiB = 8; $GateDiskGiB = 10; $FloorPhysGiB = 1.5   # plan §7.4; stop floor as P1
$NoiseForeignCpuRatio = 0.25   # predeclaration §7
$WorkerReadyChunks = 16        # two committed batches of 8 before condition B starts
$OsProcesses = @('Idle', 'System', 'Registry', 'Memory Compression', 'Secure System', 'WmiPrvSE')
$Stages = 'resources', 'commit', 'download', 'archive', 'manifest', 'extract', 'tree', 'signature', 'runtime_id', 'identity',
'provision', 'boundary', 'verify', 'tokenize', 'precision', 'seed', 'failclosed', 'warmup', 'deberta_solo', 'minilm2_solo', 'worker_start',
'deberta_concurrent', 'minilm2_concurrent', 'worker_stop', 'evaluate', 'after', 'cleanup'

$Here = $PSScriptRoot
$P1 = Join-Path (Split-Path $Here -Parent) 'p1'
$Fixture = Join-Path $Here 'fixtures\p1b-pairs-v1.json'
$Predeclaration = Join-Path $Here 'P1B_PREDECLARATION.md'
$PredeclarationV2 = Join-Path $Here 'P1B_PREDECLARATION_V2.md'
$Probe = Join-Path $Here 'p1b_probe.py'
$WorkerShim = Join-Path $Here 'p1b_worker.py'
New-Item -ItemType Directory -Path $Work -ErrorAction SilentlyContinue | Out-Null
if (Get-ChildItem -LiteralPath $Work -Force | Select-Object -First 1) { throw "work directory is not empty: $Work" }
$Work = (Resolve-Path -LiteralPath $Work).Path
$Dl = Join-Path $Work 'download'; $Runtime = Join-Path $Work 'runtime'; $Out = Join-Path $Work 'out'
$State = Join-Path $Work 'state'; $Hf = Join-Path $Work 'hf'; $Tmp = Join-Path $Work 'tmp'; $Cwd = Join-Path $Work 'cwd'
foreach ($d in $Dl, $Out, $State, $Hf, $Tmp, $Cwd, (Join-Path $Work 'settings'), (Join-Path $Work 'db')) { New-Item -ItemType Directory -Path $d | Out-Null }
$Python = Join-Path $Runtime 'python.exe'
$DbUrl = 'sqlite:///' + ((Join-Path $Work 'db\library.sqlite') -replace '\\', '/')

Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class P1bMem {
    [StructLayout(LayoutKind.Sequential)] public class MEMORYSTATUSEX {
        public uint dwLength = (uint)Marshal.SizeOf(typeof(MEMORYSTATUSEX)); public uint dwMemoryLoad;
        public ulong ullTotalPhys, ullAvailPhys, ullTotalPageFile, ullAvailPageFile, ullTotalVirtual, ullAvailVirtual, ullAvailExtendedVirtual; }
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool GlobalMemoryStatusEx([In, Out] MEMORYSTATUSEX m);
    public static double[] Mb() { var m = new MEMORYSTATUSEX(); GlobalMemoryStatusEx(m); return new double[] { m.ullAvailPhys / 1048576.0, m.ullAvailPageFile / 1048576.0 }; }
}
'@

$Checks = [System.Collections.Generic.List[object]]::new()
$Completed = [System.Collections.Generic.List[string]]::new()
$Info = [ordered]@{}
$Processes = [ordered]@{}
$Counted = [ordered]@{}
$Discarded = [ordered]@{}
$script:FirewallTouched = $false
$script:ProfilesBefore = @()
$script:Worker = $null
$script:WorkerOut = $null; $script:WorkerErr = $null

function Log([string]$m) { $line = "$(Get-Date -Format o) $m"; Write-Host $line; Add-Content -LiteralPath (Join-Path $Out 'driver.log') -Value $line }
function Add-Check([string]$Stage, [string]$Id, [string]$Kind, [bool]$Ok, $Detail = '') {
    $Checks.Add([ordered]@{ stage = $Stage; id = $Id; kind = $Kind; ok = $Ok; detail = $Detail })
    Log ("{0} {1}/{2} [{3}] {4}" -f ($(if ($Ok) { 'PASS' } else { 'FAIL' })), $Stage, $Id, $Kind, ($Detail | ConvertTo-Json -Compress -Depth 6))
    return $Ok
}
function Stage-Ok([string]$Stage) { -not ($Checks | Where-Object { $_.stage -eq $Stage -and -not $_.ok }) }
function Complete([string]$Stage) { $ok = Stage-Ok $Stage; if ($ok) { $Completed.Add($Stage) }; return $ok }
function Field($Object, [string]$Name) { $p = $Object.PSObject.Properties[$Name]; if ($p) { $p.Value } else { $null } }
function Sha256([string]$Path) { (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }
function Memory { $m = [P1bMem]::Mb(); [ordered]@{ phys_gib = [math]::Round($m[0] / 1024, 2); commit_gib = [math]::Round($m[1] / 1024, 2); phys_mb = [math]::Round($m[0]); commit_mb = [math]::Round($m[1]) } }
function Tree-Digest {
    $o = & pwsh -NoProfile -File (Join-Path $P1 'p1_tree_digest.ps1') -Root $Runtime 2>&1 | Out-String
    if ($o -match 'entries (\d+) bytes (\d+) digest ([0-9a-f]{64})') { return [ordered]@{ entries = [int64]$Matches[1]; bytes = [int64]$Matches[2]; digest = $Matches[3] } }
    return [ordered]@{ error = $o.Trim() }
}
function Cpu-Snapshot {
    $s = @{}
    foreach ($p in [System.Diagnostics.Process]::GetProcesses()) { try { $s[$p.Id] = @($p.ProcessName, $p.TotalProcessorTime.TotalSeconds) } catch { } }
    return $s
}
function New-Psi([string[]]$ArgList, [bool]$Offline, [bool]$Measure) {
    $psi = [System.Diagnostics.ProcessStartInfo]::new($Python)
    foreach ($a in $ArgList) { $psi.ArgumentList.Add($a) }
    $psi.UseShellExecute = $false; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    $psi.WorkingDirectory = $Cwd
    foreach ($k in @($psi.Environment.Keys)) {
        if ($k -match '^(HF_|HUGGING|TRANSFORMERS_|CALLOSUM_|PYTHON|ACTIONS_|GITHUB_TOKEN|TOKENIZERS_|OMP_|MKL_)') { [void]$psi.Environment.Remove($k) }
    }
    $envs = @{ HF_HOME = $Hf; HF_HUB_DISABLE_TELEMETRY = '1'; HF_HUB_DISABLE_SYMLINKS_WARNING = '1'; HF_HUB_DISABLE_PROGRESS_BARS = '1'
        CALLOSUM_MODEL_PROVISIONING_DIR = $State; CALLOSUM_SETTINGS_PATH = (Join-Path $Work 'settings\app-settings.json'); TEMP = $Tmp; TMP = $Tmp
    }
    # Measurement, fail-closed and worker processes see a provisioner-managed checkpoint, as in the packaged app.
    if ($Measure) { $envs.CALLOSUM_MODEL_PROVISIONING = '1' } else { $envs.CALLOSUM_DISABLE_MODEL_PROVISIONING = '1' }
    if ($Offline) { $envs.HF_HUB_OFFLINE = '1'; $envs.TRANSFORMERS_OFFLINE = '1' }
    foreach ($k in $envs.Keys) { $psi.Environment[$k] = $envs[$k] }
    return $psi
}

# One probe process. Samples once a second (process and worker memory, system memory), checks for child processes
# every 5 s, and snapshots every process's CPU time at start and end for the noise rule.
function Invoke-Phase([string]$Stage, [string]$Phase, [bool]$Offline, [int]$TimeoutSec, [string[]]$Extra = @(), [bool]$Measure = $false, [string]$Name = $Stage) {
    $outFile = Join-Path $Out "$Name.json"
    $psi = New-Psi (@('-I', '-B', $Probe, $Phase, '--repo', $Repo, '--work', $Work, '--state', $State, '--out', $outFile,
            '--fixture', $Fixture, '--manifest', (Join-Path $Dl 'runtime-manifest.json'), '--expected-python', $Python,
            '--python-version', $PythonVersion, '--corpus-sha256', $CorpusSha) + $Extra) $Offline $Measure
    Log "start $Name ($Phase, offline=$Offline)"
    $cpu0 = Cpu-Snapshot
    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEndAsync(); $stderr = $p.StandardError.ReadToEndAsync()
    $minPhys = [double]::MaxValue; $minCommit = [double]::MaxValue; $children = @{}; $stopped = $null; $samples = [System.Collections.Generic.List[object]]::new()
    $sw = [System.Diagnostics.Stopwatch]::StartNew(); $tick = 0
    while (-not $p.WaitForExit(1000)) {
        $tick++
        $m = Memory; $minPhys = [math]::Min($minPhys, $m.phys_gib); $minCommit = [math]::Min($minCommit, $m.commit_gib)
        $s = [ordered]@{ t = [math]::Round($sw.Elapsed.TotalSeconds, 1); avail_phys_mb = $m.phys_mb; avail_commit_mb = $m.commit_mb }
        try { $p.Refresh(); $s.ws_mb = [math]::Round($p.WorkingSet64 / 1MB, 1); $s.private_mb = [math]::Round($p.PrivateMemorySize64 / 1MB, 1); $s.cpu_s = [math]::Round($p.TotalProcessorTime.TotalSeconds, 2) } catch { }
        if ($script:Worker -and -not $script:Worker.HasExited) {
            try { $script:Worker.Refresh(); $s.worker_ws_mb = [math]::Round($script:Worker.WorkingSet64 / 1MB, 1); $s.worker_cpu_s = [math]::Round($script:Worker.TotalProcessorTime.TotalSeconds, 2) } catch { }
        }
        $samples.Add($s)
        if ($tick % 5 -eq 0) {
            foreach ($c in @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.Id)" -Property ProcessId, Name, ExecutablePath -ErrorAction SilentlyContinue)) {
                $children[[string]$c.ProcessId] = "$($c.Name) $($c.ExecutablePath)"
            }
        }
        if ($m.phys_gib -lt $FloorPhysGiB) { $stopped = "available physical memory $($m.phys_gib) GiB below the $FloorPhysGiB GiB floor" }
        elseif ($sw.Elapsed.TotalSeconds -gt $TimeoutSec) { $stopped = "timeout after $TimeoutSec s" }
        if ($stopped) { Log "stopping $Name : $stopped"; $p.Kill($true); $p.WaitForExit(); break }
    }
    $p.WaitForExit()
    $wall = $sw.Elapsed.TotalSeconds
    $cpu1 = Cpu-Snapshot
    $exclude = @($p.Id, $PID) + @($children.Keys | ForEach-Object { [int]$_ }) + @($(if ($script:Worker) { $script:Worker.Id }))
    # $procName, never $name: PowerShell names are case-insensitive, so $name would overwrite the $Name parameter
    # (run 41948518913 filed deberta_solo_1 under "MsMpEng"; p1b_driver_selftest.ps1 guards this).
    $foreign = @(foreach ($id in $cpu1.Keys) {
            $procName = $cpu1[$id][0]
            if ($exclude -contains $id -or $OsProcesses -contains $procName -or $procName -eq 'conhost') { continue }
            $before = if ($cpu0.ContainsKey($id) -and $cpu0[$id][0] -eq $procName) { $cpu0[$id][1] } else { 0 }
            $d = $cpu1[$id][1] - $before
            if ($d -gt 0.05) { [pscustomobject]@{ pid = $id; name = $procName; cpu_s = [math]::Round($d, 2) } }
        }) | Sort-Object { $_.cpu_s } -Descending
    $foreignTotal = 0.0; foreach ($f in $foreign) { $foreignTotal += $f.cpu_s }
    $peakWs = 0.0; foreach ($x in $samples) { if ($x.Contains('ws_mb')) { $peakWs = [math]::Max($peakWs, $x.ws_mb) } }
    Set-Content -LiteralPath (Join-Path $Out "$Name.stdout.txt") -Value $stdout.Result
    Set-Content -LiteralPath (Join-Path $Out "$Name.stderr.txt") -Value $stderr.Result
    $samples | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Out "$Name.samples.json")
    $unexpected = @($children.Values | Where-Object { $_ -notmatch '^conhost\.exe ' })
    $Processes[$Name] = [ordered]@{ exit_code = $p.ExitCode; seconds = [math]::Round($wall, 1); start = $p.StartTime.ToUniversalTime().ToString('o')
        sampled_peak_working_set_mib = $peakWs
        min_available_phys_gib = $minPhys; min_free_commit_gib = $minCommit; child_processes = @($children.Values); stopped = $stopped
        foreign_cpu_seconds = [math]::Round([double]$foreignTotal, 2); foreign_cpu_ratio = [math]::Round([double]$foreignTotal / [math]::Max($wall, 1e-6), 3)
        top_foreign = @($foreign | Select-Object -First 5)
    }
    [void](Add-Check $Stage "${Name}_no_unexpected_child_process" 'isolation' ($unexpected.Count -eq 0) @($children.Values))
    if ($stopped) {
        $kind = if ($Phase -eq 'measure' -and $stopped -like 'timeout*') { 'performance' } else { 'infrastructure' }   # predeclaration §7
        [void](Add-Check $Stage "${Name}_process_not_stopped" $kind $false $stopped); return $null
    }
    if (-not (Test-Path -LiteralPath $outFile)) { [void](Add-Check $Stage "${Name}_result_written" 'integrity' $false "exit $($p.ExitCode) without a result file"); return $null }
    $result = Get-Content -Raw -LiteralPath $outFile | ConvertFrom-Json -AsHashtable
    $reported = if ($result.ContainsKey('checks')) { @($result['checks']) } else { @() }
    if ($reported.Count -eq 0) { [void](Add-Check $Stage "${Name}_reported_checks" 'integrity' $false 'no checks reported') }
    $prefix = if ($Name -ne $Stage) { "${Name}:" } else { '' }
    foreach ($c in $reported) { [void](Add-Check $Stage "$prefix$($c['id'])" $c['kind'] ([bool]$c['ok']) $c['detail']) }
    return $result
}
function Phase-Stage([string]$Stage, [string]$Phase, [bool]$Offline, [int]$TimeoutSec, [bool]$Measure = $false) {
    [void](Invoke-Phase $Stage $Phase $Offline $TimeoutSec @() $Measure)
    return (Complete $Stage)
}

# One measured process under the noise rule: a discarded process is repeated once; two in a row stop the condition.
function Measure-Condition([string]$Stage, [string]$Model, [string]$Condition, [int]$Count) {
    $key = "${Model}_$Condition"; $Discarded[$key] = [System.Collections.Generic.List[string]]::new()
    $extra = @('--model', $Model, '--condition', $Condition)
    if ($Condition -eq 'concurrent') { $extra += @('--worker-pid', [string]$script:Worker.Id) }
    for ($slot = 1; $slot -le $Count; $slot++) {
        $accepted = $false
        foreach ($attempt in 1, 2) {
            $name = if ($attempt -eq 1) { "${key}_$slot" } else { "${key}_${slot}_repeat" }
            $r = Invoke-Phase $Stage 'measure' $true 900 ($extra + @('--label', $name)) $true $name
            if ($null -eq $r -or -not $r['data'].ContainsKey('resource_policy')) { return }   # the failed checks are already recorded
            if (-not $Processes.Contains($name)) { [void](Add-Check $Stage "${name}_process_record_present" 'infrastructure' $false 'harness defect: Invoke-Phase recorded no process metadata under this name'); return }
            $pr = $Processes[$name]
            $reserve = $r['data']['resource_policy']['reserve_mb']
            $lowMemory = ($pr.min_available_phys_gib * 1024) -lt $reserve
            $busy = $pr.foreign_cpu_ratio -ge $NoiseForeignCpuRatio
            $pr.noise = [ordered]@{ reserve_mb = $reserve; min_available_phys_mb = [math]::Round($pr.min_available_phys_gib * 1024); low_memory = $lowMemory; foreign_cpu_ratio = $pr.foreign_cpu_ratio; foreign_busy = $busy }
            if ($lowMemory -or $busy) { Log "noise rule: $name discarded"; $Discarded[$key].Add($name); continue }
            $Counted[$name] = Join-Path $Out "$name.json"; $accepted = $true; break
        }
        if (-not $accepted) { [void](Add-Check $Stage "${key}_slot${slot}_two_discards" 'infrastructure' $false $Discarded[$key]); return }
    }
}

function Worker-Status([string]$Name) {
    $r = Invoke-Phase 'worker_start' 'worker_status' $true 120 @() $true $Name
    if ($null -eq $r) { return $null }
    return $r['data']['row']
}

function Remove-Firewall {
    if (-not $script:FirewallTouched) { return }
    Get-NetFirewallRule -Group $FirewallGroup -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    foreach ($pr in $script:ProfilesBefore) { Set-NetFirewallProfile -Name $pr.Name -Enabled $pr.Enabled }
    $left = @(Get-NetFirewallRule -Group $FirewallGroup -ErrorAction SilentlyContinue).Count
    [void](Add-Check 'cleanup' 'firewall_rules_removed' 'infrastructure' ($left -eq 0) "$left rules left")
    $script:FirewallTouched = $false
}
function Stop-WorkerHard {
    if ($script:Worker -and -not $script:Worker.HasExited) { Log 'killing the Arctic worker'; $script:Worker.Kill($true); $script:Worker.WaitForExit() }
}

function Run-Stages {
    # resources
    $os = Get-CimInstance Win32_OperatingSystem
    $disk = (Get-PSDrive -Name ((Split-Path -Qualifier $Work).TrimEnd(':'))).Free / 1GB
    $m = Memory
    $Info.resources = [ordered]@{ total_phys_gib = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2); commit_limit_gib = [math]::Round($os.TotalVirtualMemorySize / 1MB, 2)
        available_phys_gib = $m.phys_gib; free_commit_gib = $m.commit_gib; free_disk_gib = [math]::Round($disk, 2); work_drive = (Split-Path -Qualifier $Work)
        logical_processors = (Get-CimInstance Win32_Processor | Measure-Object NumberOfLogicalProcessors -Sum).Sum
        physical_cores = (Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum
        cpu = @(Get-CimInstance Win32_Processor | ForEach-Object Name); os = $os.Caption; os_build = $os.BuildNumber
        image_os = $env:ImageOS; image_version = $env:ImageVersion; runner_name = $env:RUNNER_NAME
        job_object_limits = 'none configured by the workflow; the hosted VM is the resource boundary'
        gate = @{ phys_gib = $GatePhysGiB; commit_gib = $GateCommitGiB; disk_gib = $GateDiskGiB; stop_floor_phys_gib = $FloorPhysGiB }
    }
    $admin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    [void](Add-Check 'resources' 'available_physical_memory' 'infrastructure' ($m.phys_gib -ge $GatePhysGiB) $m.phys_gib)
    [void](Add-Check 'resources' 'free_commit' 'infrastructure' ($m.commit_gib -ge $GateCommitGiB) $m.commit_gib)
    [void](Add-Check 'resources' 'free_disk' 'infrastructure' ($disk -ge $GateDiskGiB) ([math]::Round($disk, 2)))
    [void](Add-Check 'resources' 'logical_processors_recorded' 'infrastructure' ($Info.resources.logical_processors -ge 2) $Info.resources.logical_processors)
    [void](Add-Check 'resources' 'administrator_for_firewall' 'infrastructure' $admin '')
    if (-not (Complete 'resources')) { return }

    # commit: the qualification tree is the qualified P1 commit plus this harness and the inc 637 correction, and the
    # app/tests trees equal the pinned corrected source (the integration head plus exactly the allowed files)
    $head = (git -C $Repo rev-parse HEAD).Trim()
    $Info.commit = [ordered]@{ head = $head; qualified_p1 = $QualifiedP1Commit; integration_head = $IntegrationHead; github_sha = $env:GITHUB_SHA; ref = $env:GITHUB_REF }
    [void](Add-Check 'commit' 'head_is_triggering_commit' 'integrity' ((-not $env:GITHUB_SHA) -or $head -eq $env:GITHUB_SHA) $head)
    git -C $Repo merge-base --is-ancestor $QualifiedP1Commit $head; $anc = $LASTEXITCODE -eq 0
    [void](Add-Check 'commit' 'qualified_p1_is_ancestor' 'integrity' $anc $QualifiedP1Commit)
    $changed = @(git -C $Repo diff --name-only $QualifiedP1Commit $head)
    $foreign = @($changed | Where-Object { $f = $_; -not ($AllowedChanges | Where-Object { $f -match $_ }) })
    $Info.commit.changed_files = $changed
    [void](Add-Check 'commit' 'only_p1b_harness_changed' 'integrity' ($anc -and $foreign.Count -eq 0) $foreign)
    $trees = [ordered]@{}
    foreach ($k in $TreePins.Keys) { $trees[$k] = (git -C $Repo rev-parse "HEAD:$k" 2>$null) }
    $Info.commit.trees = $trees
    $drift = @($TreePins.Keys | Where-Object { $trees[$_] -ne $TreePins[$_] })
    [void](Add-Check 'commit' 'application_trees_equal_pins' 'integrity' ($drift.Count -eq 0) $drift)
    [void](Add-Check 'commit' 'predeclaration_sha256' 'integrity' ((Sha256 $Predeclaration) -ceq $PredeclarationSha) (Sha256 $Predeclaration))
    [void](Add-Check 'commit' 'predeclaration_v2_sha256' 'integrity' ((Sha256 $PredeclarationV2) -ceq $PredeclarationV2Sha) (Sha256 $PredeclarationV2))
    [void](Add-Check 'commit' 'fixture_sha256' 'integrity' ((Sha256 $Fixture) -ceq $FixtureSha) (Sha256 $Fixture))
    $dirty = @(git -C $Repo status --porcelain)
    [void](Add-Check 'commit' 'clean_checkout' 'integrity' ($dirty.Count -eq 0) $dirty)
    $script:PycacheBefore = @(Get-ChildItem -LiteralPath $Repo -Recurse -Directory -Filter '__pycache__' -Force).Count
    if (-not (Complete 'commit')) { return }

    # download / archive / manifest / extract / tree / signature / runtime_id: as P1, P1 scripts unchanged
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        foreach ($name in "$RuntimeId.tar.gz", 'runtime-manifest.json', 'runtime-manifest.json.sig') {
            Invoke-WebRequest -Uri "$ReleaseBase/$name" -OutFile (Join-Path $Dl $name) -MaximumRetryCount 3 -RetryIntervalSec 15 -UseBasicParsing
        }
        [void](Add-Check 'download' 'runtime_release_downloaded' 'infrastructure' $true "$([math]::Round($sw.Elapsed.TotalSeconds,1)) s")
    } catch { [void](Add-Check 'download' 'runtime_release_downloaded' 'infrastructure' $false $_.Exception.Message) }
    if (-not (Complete 'download')) { return }
    $archive = Join-Path $Dl "$RuntimeId.tar.gz"
    $size = (Get-Item -LiteralPath $archive).Length; $sha = Sha256 $archive
    $Info.runtime = [ordered]@{ id = $RuntimeId; archive_url = "$ReleaseBase/$RuntimeId.tar.gz"; archive_bytes = $size; archive_sha256 = $sha }
    [void](Add-Check 'archive' 'archive_bytes' 'integrity' ($size -eq $ArchiveBytes) $size)
    [void](Add-Check 'archive' 'archive_sha256' 'integrity' ($sha -ceq $ArchiveSha) $sha)
    if (-not (Complete 'archive')) { return }
    $mf = Get-Content -Raw -LiteralPath (Join-Path $Dl 'runtime-manifest.json') | ConvertFrom-Json
    $Info.runtime.manifest_sha256 = Sha256 (Join-Path $Dl 'runtime-manifest.json')
    foreach ($pair in @(@('runtime_id', $RuntimeId), @('archive_sha256', $ArchiveSha), @('archive_bytes', $ArchiveBytes), @('tree_sha256', $TreeSha),
            @('entry_count', $EntryCount), @('unpacked_bytes', $UnpackedBytes), @('python_relative_path', 'python.exe'), @('python_version', $PythonVersion))) {
        $value = Field $mf $pair[0]
        [void](Add-Check 'manifest' "manifest_$($pair[0])" 'integrity' ($null -ne $value -and "$value" -ceq "$($pair[1])") $value)
    }
    if (-not (Complete 'manifest')) { return }
    $x = & pwsh -NoProfile -File (Join-Path $P1 'p1_extract_runtime.ps1') -Archive $archive -Dest $Runtime -ManifestPath (Join-Path $Dl 'runtime-manifest.json') -ListOut (Join-Path $Out 'extracted-entries.txt') 2>&1 | Out-String
    $xc = $LASTEXITCODE; Set-Content -LiteralPath (Join-Path $Out 'extract.log') -Value $x
    [void](Add-Check 'extract' 'safe_extraction_stream_digest' 'integrity' ($xc -eq 0 -and $x -match 'EXTRACT-STREAM TREE MATCH') ($x.Trim() -split "`n" | Select-Object -Last 2))
    if (-not (Complete 'extract')) { return }
    $t = Tree-Digest; $Info.runtime.tree_before = $t
    [void](Add-Check 'tree' 'runtime_tree_sha256' 'integrity' ($t.Contains('digest') -and $t.digest -ceq $TreeSha -and $t.entries -eq $EntryCount -and $t.bytes -eq $UnpackedBytes) $t)
    if (-not (Complete 'tree')) { return }
    $s = & $Python -I -B (Join-Path $P1 'p1_minisign.py') (Join-Path $Dl 'runtime-manifest.json') (Join-Path $Dl 'runtime-manifest.json.sig') (Join-Path $Repo 'app\desktop-shell\src-tauri\src\python_runtime.rs') 2>&1 | Out-String
    [void](Add-Check 'signature' 'manifest_signature' 'integrity' ($LASTEXITCODE -eq 0 -and $s -match 'SIGNATURE OK') $s.Trim())
    if (-not (Complete 'signature')) { return }
    $rid = (& $Python -I -B (Join-Path $Repo 'app\desktop-shell\packaging\package_python_runtime.py') id --platform windows-x86_64 2>&1 | Out-String).Trim()
    [void](Add-Check 'runtime_id' 'committed_inputs_name_runtime' 'integrity' ($rid -ceq $RuntimeId) $rid)
    if (-not (Complete 'runtime_id')) { return }

    if (-not (Phase-Stage 'identity' 'identity' $false 300)) { return }
    if (-not (Phase-Stage 'provision' 'provision' $false 2400)) { return }
    Copy-Item -LiteralPath (Join-Path $State 'baseline-inventory.json') -Destination (Join-Path $Out 'baseline-inventory.json')

    # boundary: block the exact interpreter image, then prove the block with negative and positive controls
    $script:ProfilesBefore = @(Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultOutboundAction)
    $Info.firewall_profiles_before = $script:ProfilesBefore
    $script:FirewallTouched = $true
    Set-NetFirewallProfile -Profile Domain, Private, Public -Enabled True
    New-NetFirewallRule -Name "callosum-p1b-$($env:GITHUB_RUN_ID)-$($env:GITHUB_RUN_ATTEMPT)" -DisplayName 'callosum P1b offline boundary' -Group $FirewallGroup `
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
    [void](Invoke-Phase 'boundary' 'netcheck' $true 300 @('--target-ip', $ip, '--target-hosts', 'huggingface.co', 'github.com') $false 'netcheck')
    $Info.boundary = [ordered]@{ mechanism = 'Windows Firewall outbound block rule on the exact interpreter path (covers the worker, same image)'; target_ip = $ip }
    if (-not (Complete 'boundary')) { return }   # never claim offline results without a demonstrated block

    if (-not (Phase-Stage 'verify' 'verify' $true 900)) { return }
    if (-not (Phase-Stage 'tokenize' 'tokenize' $true 600)) { return }   # before any timed call
    # precision (v2 §3): float32 requested, verified on the loaded parameters, CPU/torch, pinned checkpoint, P1 parity.
    # A failure here stops the run before seed, warm-up or any measured process.
    if (-not (Phase-Stage 'precision' 'precision' $true 900 $true)) { return }
    if (-not (Phase-Stage 'seed' 'seed' $true 1800)) { return }
    if (-not (Phase-Stage 'failclosed' 'failclosed' $true 900 $true)) { return }

    # warm-up: one discarded process per model (file cache, MiniLM chunk vectors); its functional checks still count
    foreach ($model in 'deberta', 'minilm2') { [void](Invoke-Phase 'warmup' 'measure' $true 1200 @('--model', $model, '--condition', 'solo', '--label', "${model}_warmup") $true "${model}_warmup") }
    if (-not (Complete 'warmup')) { return }

    Measure-Condition 'deberta_solo' 'deberta' 'solo' 3; [void](Complete 'deberta_solo')
    Measure-Condition 'minilm2_solo' 'minilm2' 'solo' 3; [void](Complete 'minilm2_solo')

    # worker_start: arm the run row as IndexSupervisor does, launch the production worker, wait for two batches
    $arm = Invoke-Phase 'worker_start' 'arm_worker' $true 300 @() $true 'arm_worker'
    if ($null -ne $arm -and (Stage-Ok 'worker_start')) {
        $token = (Get-Content -Raw -LiteralPath (Join-Path $State 'worker-token')).Trim()
        $wargs = @('-I', '-B', $WorkerShim, $Repo, '--db-url', $DbUrl, '--profile', 'arctic-s', '--token', $token, '--batch-size', '8',
            '--parent-pid', [string]$PID, '--threads', '4', '--local-files-only')
        $wpsi = New-Psi $wargs $true $true
        $script:Worker = [System.Diagnostics.Process]::Start($wpsi)
        $script:WorkerOut = $script:Worker.StandardOutput.ReadToEndAsync(); $script:WorkerErr = $script:Worker.StandardError.ReadToEndAsync()
        $script:Worker.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
        $Info.worker = [ordered]@{ pid = $script:Worker.Id; started = $script:Worker.StartTime.ToUniversalTime().ToString('o'); priority = "$($script:Worker.PriorityClass)"
            argv = ($wargs | Where-Object { $_ -ne $token }); entry = 'app.backend.embeddings.index_worker.main via p1b_worker.py'; threads = 4; batch_size = 8 }
        $deadline = (Get-Date).AddSeconds(600); $ready = $null; $poll = 0
        while ((Get-Date) -lt $deadline -and -not $script:Worker.HasExited) {
            Start-Sleep -Seconds 10; $poll++
            $row = Worker-Status "worker_status_$poll"
            if ($row -and $row['state'] -eq 'running' -and [int]$row['indexed_chunks'] -ge $WorkerReadyChunks -and [int]$row['worker_pid'] -eq $script:Worker.Id) { $ready = $row; break }
        }
        $Info.worker.ready_row = $ready
        [void](Add-Check 'worker_start' 'worker_claimed_row_and_indexing' 'infrastructure' ($null -ne $ready) $(if ($ready) { $ready } else { "exited=$($script:Worker.HasExited)" }))
    }
    if (-not (Complete 'worker_start')) { Stop-WorkerHard; return }

    Measure-Condition 'deberta_concurrent' 'deberta' 'concurrent' 3; [void](Complete 'deberta_concurrent')
    Measure-Condition 'minilm2_concurrent' 'minilm2' 'concurrent' 1; [void](Complete 'minilm2_concurrent')

    # worker_stop: the run row's pause intent; the worker must exit between batches with code 3
    [void](Invoke-Phase 'worker_stop' 'stop_worker' $true 120 @() $true 'stop_worker')
    $exited = $script:Worker.WaitForExit(120000)
    if (-not $exited) { Stop-WorkerHard }
    $Info.worker.exit_code = $script:Worker.ExitCode; $Info.worker.exited_on_request = $exited
    $Info.worker.ended = $script:Worker.ExitTime.ToUniversalTime().ToString('o')
    Set-Content -LiteralPath (Join-Path $Out 'worker.stdout.txt') -Value $script:WorkerOut.Result
    Set-Content -LiteralPath (Join-Path $Out 'worker.stderr.txt') -Value $script:WorkerErr.Result
    [void](Add-Check 'worker_stop' 'worker_exited_on_pause_request' 'infrastructure' ($exited -and $script:Worker.ExitCode -eq 3) "exited=$exited code=$($script:Worker.ExitCode)")
    $final = Invoke-Phase 'worker_stop' 'worker_status' $true 120 @() $true 'worker_status_final'
    if ($final) { $Info.worker.final_row = $final['data']['row'] }
    [void](Complete 'worker_stop')

    # evaluate: the predeclared aggregation over the counted processes
    $plan = [ordered]@{ counted = $Counted; discarded = $Discarded }
    $plan | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Out 'evaluation-plan.json')
    $ev = Invoke-Phase 'evaluate' 'evaluate' $true 300 @('--plan', (Join-Path $Out 'evaluation-plan.json'))
    if ($ev) { $Info.evaluation = $ev['data']['summary'] }
    [void](Complete 'evaluate')

    # after: nothing the probes ran may have changed the runtime, the checkpoints or the checkout
    $t2 = Tree-Digest; $Info.runtime.tree_after = $t2
    [void](Add-Check 'after' 'runtime_tree_unchanged' 'integrity' ($t2.Contains('digest') -and $t2.digest -ceq $TreeSha) $t2)
    [void](Invoke-Phase 'after' 'verify' $true 900 @() $false 'verify_after')
    $pyc = @(Get-ChildItem -LiteralPath $Repo -Recurse -Directory -Filter '__pycache__' -Force).Count
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
    try { Stop-WorkerHard } catch { [void](Add-Check 'cleanup' 'worker_cleanup_exception' 'infrastructure' $false $_.Exception.Message) }
    try { Remove-Firewall } catch { [void](Add-Check 'cleanup' 'firewall_cleanup_exception' 'infrastructure' $false $_.Exception.Message) }
    if (-not ($Checks | Where-Object { $_.stage -eq 'cleanup' -and -not $_.ok })) { $Completed.Add('cleanup') }
}

$failed = @($Checks | Where-Object { -not $_.ok })
$hard = @($failed | Where-Object { $_.kind -ne 'infrastructure' })
$missing = @($Stages | Where-Object { $Completed -notcontains $_ })
$verdict = if ($hard.Count) { 'FAIL' } elseif ($failed.Count -or $missing.Count) { 'INCONCLUSIVE' } else { 'PASS' }
$receipt = [ordered]@{
    schema = 'callosum-p1b-qualification-receipt-v2'; stage = 'P1b packaged DeBERTa performance and resource qualification (Windows x64), revision 2: float32 DeBERTa loading (inc 637)'
    verdict = $verdict; started = $started.ToString('o'); finished = (Get-Date).ToString('o')
    run = [ordered]@{ repository = $env:GITHUB_REPOSITORY; ref = $env:GITHUB_REF; sha = $env:GITHUB_SHA; run_id = $env:GITHUB_RUN_ID; attempt = $env:GITHUB_RUN_ATTEMPT; workflow = $env:GITHUB_WORKFLOW; runner = $env:RUNNER_NAME
        url = "$($env:GITHUB_SERVER_URL)/$($env:GITHUB_REPOSITORY)/actions/runs/$($env:GITHUB_RUN_ID)" }
    predeclaration = [ordered]@{ path = 'tools/qualification/p1b/P1B_PREDECLARATION.md'; sha256 = (Sha256 $Predeclaration)
        revision = [ordered]@{ path = 'tools/qualification/p1b/P1B_PREDECLARATION_V2.md'; sha256 = (Sha256 $PredeclarationV2) }
        first_attempt = 'run 41948518913 at 7998ea63: INCONCLUSIVE (driver defect); float16 DeBERTa; not this experiment' }
    fixture = [ordered]@{ path = 'tools/qualification/p1b/fixtures/p1b-pairs-v1.json'; sha256 = (Sha256 $Fixture); indexing_corpus_sha256 = $CorpusSha }
    models = [ordered]@{ deberta = 'MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli@6f5cf0a2b59cabb106aca4c287eed12e357e90eb (committed manifest; loaded with dtype=torch.float32, verified on the loaded parameters)'
        arctic_s = 'Snowflake/snowflake-arctic-embed-s@e596f507467533e48a2e17c007f0e1dacc837b33 (committed manifest)'
        minilm = 'sentence-transformers/all-MiniLM-L6-v2@1110a243fdf4706b3f48f1d95db1a4f5529b4d41 (run inventory, no committed manifest)'
        minilm2 = 'cross-encoder/nli-MiniLM2-L6-H768@b95119ce93d3e065de6214e38cd4a97b0f2f2c6d (run inventory, no committed manifest)' }
    harness_sha256 = [ordered]@{ driver = (Sha256 $PSCommandPath); probe = (Sha256 $Probe); worker_shim = (Sha256 $WorkerShim); p1_extract = (Sha256 (Join-Path $P1 'p1_extract_runtime.ps1')); p1_tree = (Sha256 (Join-Path $P1 'p1_tree_digest.ps1')); p1_minisign = (Sha256 (Join-Path $P1 'p1_minisign.py')); p1_probe = (Sha256 (Join-Path $P1 'p1_probe.py')) }
    info = $Info; processes = $Processes; counted = $Counted; discarded = $Discarded; stages_completed = $Completed; stages_missing = $missing
    failed_checks = $failed; checks = $Checks
    limitations = @(
        'The 21 pairs are a new public synthetic fixture. They do not reproduce G2''s pairs; the comparison with G2 is envelope-level.',
        'G1 categorical parity (99 + 209 private pairs, plan §8.2) is not covered: the private material is not published to GitHub Actions. G1 stays CONDITIONAL, and the float32 loader needs its own G1 re-check.',
        'The precision stage''s P1 parity uses two synthetic pairs and the P1 limit (0.001); it shows the corrected loader reproduces the float32 reference, not G1 parity. Float16 outputs also fall within 0.001: the precision evidence is the loaded-parameter check, not the parity tolerance.',
        'Passing operational limits says nothing about threshold calibration.',
        'MiniLM and MiniLM2 are checked against an inventory taken in this run at the pinned revision, not against a committed manifest.',
        'The Arctic worker is the production worker entry under a -I -B shim, without the supervisor; supervisor retry and restart are P3.',
        'Fail-closed behaviour under resource pressure is shown with simulated memory snapshots and an injected inference failure, not real exhaustion.',
        'One hosted VM (4 vCPU class, 16 GB). Not 8 GB machines, macOS or Linux.',
        'The outbound block applies to the exact python.exe image; DNS resolution by the Windows DNS Client service can still leave the VM.'
    )
    not_covered = @('arming DEBERTA_RELEASE_GATES.packaged_runtime_acceptance (a product decision)', 'G1 scientific parity on the packaged runtime', 'P2 packaged backend', 'P3 worker lifecycle and recovery', 'P4 installed Tauri application', 'macOS and Linux', 'Issue #110', 'independent security review', 'the 0.6.0 release gate')
}
$receipt | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath (Join-Path $Out 'p1b-receipt.json') -Encoding utf8NoBOM
$summary = @("## P1b qualification: $verdict", '', "Commit $($env:GITHUB_SHA), runtime $RuntimeId", '', "Stages completed: $($Completed -join ', ')", "Stages missing: $($missing -join ', ')", '')
if ($Info.Contains('evaluation')) {
    foreach ($c in 'deberta_solo', 'deberta_concurrent') {
        $e = $Info.evaluation['conditions'][$c]
        if ($e -and $e.Contains('acceptance_statistic_s')) { $summary += "- $c : largest process median $([math]::Round($e['acceptance_statistic_s'], 3)) s (limit $($e['limit_s']) s), evaluated=$($e['evaluated'])" }
    }
    if ($Info.evaluation.Contains('memory')) { $summary += "- peak working set $([math]::Round($Info.evaluation['memory']['peak_working_set_mb'])) MB (limit 2520), peak commit $([math]::Round($Info.evaluation['memory']['peak_commit_mb'])) MB (limit 2870)" }
}
$summary += @('', '| stage | check | kind | detail |', '|---|---|---|---|')
foreach ($f in $failed) {
    $d = (ConvertTo-Json -InputObject $f.detail -Compress -Depth 4) -replace '\|', '/'
    $summary += "| $($f.stage) | $($f.id) | $($f.kind) | $($d.Substring(0, [math]::Min(300, $d.Length))) |"
}
$summary | Set-Content -LiteralPath (Join-Path $Out 'p1b-summary.md') -Encoding utf8NoBOM
if ($env:GITHUB_STEP_SUMMARY) { $summary | Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY }
if ($env:GITHUB_OUTPUT) { "verdict=$verdict" | Add-Content -LiteralPath $env:GITHUB_OUTPUT }
Log "VERDICT $verdict ($($failed.Count) failed checks, missing stages: $($missing -join ','))"
exit $(switch ($verdict) { 'PASS' { 0 } 'FAIL' { 1 } default { 2 } })
