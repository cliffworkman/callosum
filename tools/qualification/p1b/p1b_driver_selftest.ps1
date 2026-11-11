# Model-free regression test for the P1b driver's process bookkeeping (inc 636 follow-up).
#
# Run 41948518913 stored deberta_solo_1's record under "MsMpEng": Invoke-Phase's CPU-accounting loop assigned $name,
# which in PowerShell is the same variable as its $Name parameter. This test loads the driver's own function
# definitions from the AST (it never runs the driver, a model or the runtime), replaces only the OS-facing helpers
# with deterministic fakes, and starts a trivial cmd.exe child in place of the probe.
# Usage: pwsh -NoProfile -File p1b_driver_selftest.ps1   (exit 0 when every check passes)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3

$Driver = Join-Path $PSScriptRoot 'p1b_qualify.ps1'
$errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Driver, [ref]$null, [ref]$errs)
if (@($errs).Count) { throw "driver does not parse: $errs" }
$functions = @{}
foreach ($f in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)) { $functions[$f.Name] = $f }

$Results = [System.Collections.Generic.List[object]]::new()
function Test([string]$Id, [bool]$Ok, $Detail = '') { $Results.Add([pscustomobject]@{ id = $Id; ok = $Ok; detail = $Detail }) }

# --- 1. static: no function assigns a variable that is one of its parameters under another spelling --------------
foreach ($f in $functions.Values) {
    $params = @{}
    $declared = if ($f.Parameters) { $f.Parameters } elseif ($f.Body.ParamBlock) { $f.Body.ParamBlock.Parameters } else { @() }
    foreach ($p in $declared) { $params[$p.Name.VariablePath.UserPath.ToLowerInvariant()] = $p.Name.VariablePath.UserPath }
    $targets = @($f.Body.FindAll({ param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst] }, $true) |
            ForEach-Object { $_.Left } | Where-Object { $_ -is [System.Management.Automation.Language.VariableExpressionAst] })
    $targets += @($f.Body.FindAll({ param($n) $n -is [System.Management.Automation.Language.ForEachStatementAst] }, $true) | ForEach-Object { $_.Variable })
    $clash = @(foreach ($t in $targets) {
            $u = $t.VariablePath.UserPath
            if ($params.ContainsKey($u.ToLowerInvariant()) -and $params[$u.ToLowerInvariant()] -cne $u) { "$($f.Name): `$$u overwrites parameter `$$($params[$u.ToLowerInvariant()]) (line $($t.Extent.StartLineNumber))" }
        })
    Test "no_parameter_shadowing_$($f.Name)" ($clash.Count -eq 0) $clash
}

# --- 2. load the driver's real functions; fake only process start, CPU snapshots and memory ------------------------
foreach ($n in 'Log', 'Add-Check', 'Invoke-Phase', 'Measure-Condition') { . ([scriptblock]::Create($functions[$n].Extent.Text)) }
$Out = Join-Path ([System.IO.Path]::GetTempPath()) ("p1b-driver-selftest-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Out | Out-Null
$Checks = [System.Collections.Generic.List[object]]::new()
$Processes = [ordered]@{}; $Counted = [ordered]@{}; $Discarded = [ordered]@{}
$OsProcesses = @('Idle', 'System', 'Registry', 'Memory Compression', 'Secure System', 'WmiPrvSE')
$NoiseForeignCpuRatio = 0.25; $FloorPhysGiB = 1.5
$script:Worker = $null
$Probe = 'probe.py'; $Repo = 'repo'; $Work = 'work'; $State = 'state'; $Fixture = 'fixture.json'; $Dl = 'dl'
$Python = 'python.exe'; $PythonVersion = '3.11.15'; $CorpusSha = '0' * 64

function Memory { [ordered]@{ phys_gib = 12.0; commit_gib = 14.0; phys_mb = 12288; commit_mb = 14336 } }
# Every process in both snapshots has a foreign name, so whichever the loop visits last is not the measured label.
$script:Snap = 0
function Cpu-Snapshot {
    $script:Snap++
    $t = if ($script:Snap % 2) { 1.0 } else { 1.1 }   # 0.1 CPU-s each: recorded (> 0.05) but under the 0.25/s noise rule
    @{ 900001 = @('MsMpEng', $t); 900002 = @('WindowsTerminal', $t); 900003 = @('deberta_solo_9', $t); 4 = @('System', $t) }
}
# Writes the probe's result file in place of p1b_probe.py and starts cmd.exe, which echoes the label to stdout.
function New-Psi([string[]]$ArgList, [bool]$Offline, [bool]$Measure) {
    $outFile = $ArgList[[array]::IndexOf($ArgList, '--out') + 1]
    $li = [array]::IndexOf($ArgList, '--label'); $label = if ($li -ge 0) { $ArgList[$li + 1] } else { 'nolabel' }
    $res = [ordered]@{ phase = 'measure'; checks = @([ordered]@{ id = 'statuses_stable_across_calls'; kind = 'scientific'; ok = $true; detail = $label })
        data = [ordered]@{ label = $label; resource_policy = [ordered]@{ reserve_mb = 818 } }
    }
    $res | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outFile
    $psi = [System.Diagnostics.ProcessStartInfo]::new($env:ComSpec)
    # ping holds the child past one 1 s sampling tick, so the driver writes a samples file as for a real probe.
    foreach ($a in '/d', '/c', "ping -n 3 127.0.0.1 >nul & echo stdout-of-$label") { $psi.ArgumentList.Add($a) }
    $psi.UseShellExecute = $false; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    return $psi
}

try {
    # --- 3. one measured process keeps the caller's identity -------------------------------------------------------
    $r = Invoke-Phase 'deberta_solo' 'measure' $true 60 @('--label', 'deberta_solo_1') $true 'deberta_solo_1' 6>$null
    Test 'record_keyed_by_caller_name' ($Processes.Contains('deberta_solo_1')) @($Processes.Keys)
    Test 'no_record_under_foreign_name' (-not ($Processes.Keys | Where-Object { $_ -in 'MsMpEng', 'WindowsTerminal', 'System', 'deberta_solo_9' })) @($Processes.Keys)
    $files = @(Get-ChildItem -LiteralPath $Out -Name)
    foreach ($s in 'json', 'stdout.txt', 'stderr.txt', 'samples.json') { Test "file_deberta_solo_1.$s" ($files -contains "deberta_solo_1.$s") $files }
    Test 'no_diagnostic_file_under_foreign_name' (-not ($files | Where-Object { $_ -match '^(MsMpEng|WindowsTerminal|System|deberta_solo_9)\.' })) $files
    Test 'check_ids_prefixed_by_caller_name' (@($Checks | Where-Object { $_.id -eq 'deberta_solo_1:statuses_stable_across_calls' }).Count -eq 1) @($Checks | ForEach-Object id)
    $top = if ($Processes.Contains('deberta_solo_1')) { @($Processes['deberta_solo_1'].top_foreign | ForEach-Object name) } else { @() }
    Test 'foreign_cpu_still_attributed_to_foreign_names' (($top -contains 'MsMpEng') -and ($top -contains 'WindowsTerminal') -and ($top -notcontains 'System')) $top
    Test 'result_returned' ($null -ne $r -and $r['data']['label'] -eq 'deberta_solo_1')

    # --- 4. three measured processes through Measure-Condition never overwrite one another --------------------------
    $Checks.Clear(); $Processes.Clear(); $Counted.Clear()
    $threw = $null
    try { Measure-Condition 'deberta_solo' 'deberta' 'solo' 3 6>$null } catch { $threw = "$_" }
    Test 'measure_condition_no_exception' ($null -eq $threw) $threw
    $want = 'deberta_solo_1', 'deberta_solo_2', 'deberta_solo_3'
    Test 'three_distinct_records' ((@($Processes.Keys) -join ',') -eq ($want -join ',')) @($Processes.Keys)
    Test 'three_counted' ((@($Counted.Keys) -join ',') -eq ($want -join ',')) @($Counted.Keys)
    foreach ($w in $want) {
        $so = Join-Path $Out "$w.stdout.txt"
        Test "own_stdout_$w" ((Test-Path -LiteralPath $so) -and ((Get-Content -Raw -LiteralPath $so) -match "stdout-of-$w\b")) $so
        Test "own_samples_$w" (Test-Path -LiteralPath (Join-Path $Out "$w.samples.json"))
        Test "noise_recorded_$w" ($Processes.Contains($w) -and $Processes[$w].Contains('noise') -and -not $Processes[$w].noise.low_memory -and -not $Processes[$w].noise.foreign_busy)
    }

    # --- 5. a missing process record is an explicit harness failure, not a property exception -----------------------
    $Checks.Clear(); $Processes.Clear(); $Counted.Clear()
    $real = $functions['Invoke-Phase'].Extent.Text
    function Invoke-Phase { return @{ data = @{ resource_policy = @{ reserve_mb = 818 } } } }   # returns a result, records nothing
    $threw = $null
    try { Measure-Condition 'deberta_solo' 'deberta' 'solo' 3 6>$null } catch { $threw = "$_" }
    . ([scriptblock]::Create($real))
    Test 'missing_record_no_exception' ($null -eq $threw) $threw
    $miss = @($Checks | Where-Object { -not $_.ok })
    Test 'missing_record_explicit_check' ($miss.Count -eq 1 -and $miss[0].id -eq 'deberta_solo_1_process_record_present' -and $miss[0].kind -eq 'infrastructure') @($miss | ForEach-Object { "$($_.id) [$($_.kind)]" })
    Test 'missing_record_nothing_counted' ($Counted.Count -eq 0) @($Counted.Keys)
}
finally {
    Remove-Item -LiteralPath $Out -Recurse -Force -ErrorAction SilentlyContinue
}

$failed = @($Results | Where-Object { -not $_.ok })
foreach ($t in $Results) { "{0} {1} {2}" -f $(if ($t.ok) { 'PASS' } else { 'FAIL' }), $t.id, $(if ($t.ok) { '' } else { ($t.detail | ConvertTo-Json -Compress -Depth 4) }) }
"`n$($Results.Count - $failed.Count)/$($Results.Count) driver self-test checks passed"
exit $(if ($failed.Count) { 1 } else { 0 })
