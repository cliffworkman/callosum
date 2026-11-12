# Model-free regression test for the P1b driver's process bookkeeping (inc 636 follow-up), its foreign-CPU noise rule
# and the V3 idle-settling check (inc 639, P1B_PREDECLARATION_V3.md).
#
# Run 41948518913 stored deberta_solo_1's record under "MsMpEng": Invoke-Phase's CPU-accounting loop assigned $name,
# which in PowerShell is the same variable as its $Name parameter. This test loads the driver's own function
# definitions from the AST (it never runs the driver, a model or the runtime), dot-sources the real p1b_noise.ps1,
# replaces only the OS-facing helpers with deterministic fakes, and starts a trivial cmd.exe child in place of the
# probe. Settling is driven with synthetic CPU snapshots and a simulated clock: nothing here waits for real time.
# Usage: pwsh -NoProfile -File p1b_driver_selftest.ps1   (exit 0 when every check passes)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3

$Driver = Join-Path $PSScriptRoot 'p1b_qualify.ps1'
$errs = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Driver, [ref]$null, [ref]$errs)
if (@($errs).Count) { throw "driver does not parse: $errs" }
$functions = @{}
foreach ($f in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)) { $functions[$f.Name] = $f }
$noiseAst = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'p1b_noise.ps1'), [ref]$null, [ref]$errs)
if (@($errs).Count) { throw "p1b_noise.ps1 does not parse: $errs" }
foreach ($f in $noiseAst.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)) { $functions[$f.Name] = $f }

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

# --- 2. load the driver's real functions and the real noise module; fake only process start, CPU, clock, memory ----
. (Join-Path $PSScriptRoot 'p1b_noise.ps1')
foreach ($n in 'Log', 'Add-Check', 'Invoke-Phase', 'Measure-Condition') { . ([scriptblock]::Create($functions[$n].Extent.Text)) }
$Out = Join-Path ([System.IO.Path]::GetTempPath()) ("p1b-driver-selftest-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Out | Out-Null
$Checks = [System.Collections.Generic.List[object]]::new()
$Processes = [ordered]@{}; $Counted = [ordered]@{}; $Discarded = [ordered]@{}; $Settling = [ordered]@{}
$FloorPhysGiB = 1.5
$script:Worker = $null
$Probe = 'probe.py'; $Repo = 'repo'; $Work = 'work'; $State = 'state'; $Fixture = 'fixture.json'; $Dl = 'dl'
$Python = 'python.exe'; $PythonVersion = '3.11.15'; $CorpusSha = '0' * 64

# Simulated monotonic clock: only the fake sleep advances it.
$script:Now = 0.0
$script:Clock = { $script:Now }
$script:SleepFor = { param([double]$Seconds) $script:Now += $Seconds }
$script:SettleBudget = @{ total_s = $SettleTotalSec; used_s = 0.0 }

function Memory { [ordered]@{ phys_gib = 12.0; commit_gib = 14.0; phys_mb = 12288; commit_mb = 14336 } }
# Every process has a foreign name, so whichever the loop visits last is not the measured label. Counters only grow
# (0.1 CPU-s per snapshot): far under both the 0.20 settling screen and the 0.25 noise rule.
$script:Snap = 0
function Cpu-Snapshot {
    $script:Snap++
    $t = 1.0 + 0.1 * $script:Snap
    @{ 900001 = @{ name = 'MsMpEng'; cpu_s = $t; start = 1 }; 900002 = @{ name = 'WindowsTerminal'; cpu_s = $t; start = 2 }
        900003 = @{ name = 'deberta_solo_9'; cpu_s = $t; start = 3 }; 4 = @{ name = 'System'; cpu_s = 50 * $t; start = 4 } }
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
function Reset-State { $Checks.Clear(); $Processes.Clear(); $Counted.Clear(); $Discarded.Clear(); $Settling.Clear(); $script:Now = 0.0; $script:SettleBudget = @{ total_s = $SettleTotalSec; used_s = 0.0 } }
function Snap([hashtable]$Cpu) { $s = @{}; foreach ($k in $Cpu.Keys) { $v = $Cpu[$k]; $s[[int]$k] = @{ name = $v[0]; cpu_s = $v[1]; start = $(if ($v.Count -gt 2) { $v[2] } else { 7 }) } }; return $s }
# A settling snapshot source from a list of per-window foreign CPU increments for one process (CPU-s per 10 s window).
function Window-Source([double[]]$PerWindow, [string]$ProcName = 'svchost') {
    $state = @{ i = 0; cpu = 100.0; rates = $PerWindow }
    return { $i = $state.i; if ($i -gt 0) { $r = $state.rates[[math]::Min($i - 1, $state.rates.Count - 1)]; $state.cpu += $r }; $state.i++
        @{ 6820 = @{ name = $ProcName; cpu_s = $state.cpu; start = 11 }; 2744 = @{ name = 'WindowsTerminal'; cpu_s = 5.0 + 0.6 * $i; start = 12 }; 0 = @{ name = 'Idle'; cpu_s = 1e6 + 40 * $i; start = $null } } }.GetNewClosure()
}
function Settle([scriptblock]$Source, [hashtable]$Budget = @{ total_s = 600.0; used_s = 0.0 }) {
    $script:Now = 0.0
    Wait-IdleSettled -Budget $Budget -Snapshot $Source -Clock $script:Clock -Sleep $script:SleepFor
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
    $top = if ($Processes.Contains('deberta_solo_1')) { @($Processes['deberta_solo_1'].top_foreign | ForEach-Object { $_.name }) } else { @() }
    Test 'foreign_cpu_still_attributed_to_foreign_names' (($top -contains 'MsMpEng') -and ($top -contains 'WindowsTerminal') -and ($top -notcontains 'System')) $top
    Test 'process_record_has_individual_and_aggregate' ($Processes.Contains('deberta_solo_1') -and $Processes['deberta_solo_1'].Contains('foreign_cpu_max_process_ratio') -and $Processes['deberta_solo_1'].Contains('foreign_cpu_ratio') -and $Processes['deberta_solo_1'].foreign_measurement_valid)
    Test 'result_returned' ($null -ne $r -and $r['data']['label'] -eq 'deberta_solo_1')

    # --- 4. three measured processes through Measure-Condition never overwrite one another --------------------------
    Reset-State
    $threw = $null
    try { Measure-Condition 'deberta_solo' 'deberta' 'solo' 3 6>$null } catch { $threw = "$_" }
    Test 'measure_condition_no_exception' ($null -eq $threw) $threw
    $want = 'deberta_solo_1', 'deberta_solo_2', 'deberta_solo_3'
    Test 'three_distinct_records' ((@($Processes.Keys) -join ',') -eq ($want -join ',')) @($Processes.Keys)
    Test 'three_counted' ((@($Counted.Keys) -join ',') -eq ($want -join ',')) @($Counted.Keys)
    Test 'settling_keyed_by_measured_name' ((@($Settling.Keys) -join ',') -eq ($want -join ',')) @($Settling.Keys)
    foreach ($w in $want) {
        $so = Join-Path $Out "$w.stdout.txt"
        Test "own_stdout_$w" ((Test-Path -LiteralPath $so) -and ((Get-Content -Raw -LiteralPath $so) -match "stdout-of-$w\b")) $so
        Test "own_samples_$w" (Test-Path -LiteralPath (Join-Path $Out "$w.samples.json"))
        Test "own_settling_file_$w" (Test-Path -LiteralPath (Join-Path $Out "$w.settling.json"))
        Test "settled_three_windows_$w" ($Settling.Contains($w) -and $Settling[$w].settled -and $Settling[$w].windows.Count -eq 3)
        Test "noise_recorded_$w" ($Processes.Contains($w) -and $Processes[$w].Contains('noise') -and -not $Processes[$w].noise.low_memory -and -not $Processes[$w].noise.foreign_busy -and $Processes[$w].noise.idle_settled_before)
        Test "settled_check_$w" (@($Checks | Where-Object { $_.id -eq "${w}_idle_settled" -and $_.ok }).Count -eq 1)
    }
    $files = @(Get-ChildItem -LiteralPath $Out -Name)
    Test 'no_settling_file_under_foreign_name' (-not ($files | Where-Object { $_ -match '^(MsMpEng|WindowsTerminal|System|svchost|deberta_solo_9)\.' })) $files
    Test 'settling_untimed_budget_charged' ([math]::Abs($script:SettleBudget.used_s - 90.0) -lt 1e-9) $script:SettleBudget.used_s

    # --- 5. a missing process record is an explicit harness failure, not a property exception -----------------------
    Reset-State
    function Invoke-Phase { return @{ data = @{ resource_policy = @{ reserve_mb = 818 } } } }   # returns a result, records nothing
    $threw = $null
    try { Measure-Condition 'deberta_solo' 'deberta' 'solo' 3 6>$null } catch { $threw = "$_" }
    Test 'missing_record_no_exception' ($null -eq $threw) $threw
    $miss = @($Checks | Where-Object { -not $_.ok })
    Test 'missing_record_explicit_check' ($miss.Count -eq 1 -and $miss[0].id -eq 'deberta_solo_1_process_record_present' -and $miss[0].kind -eq 'infrastructure') @($miss | ForEach-Object { "$($_.id) [$($_.kind)]" })
    Test 'missing_record_nothing_counted' ($Counted.Count -eq 0) @($Counted.Keys)

    # --- 6. the v1 §7 noise rule is per individual foreign process (v3 §2) ------------------------------------------
    $b = Snap @{ 101 = @('svchost', 10.0); 102 = @('MsMpEng', 10.0); 4 = @('System', 10.0); 9001 = @('pwsh', 10.0) }
    $m = Measure-ForeignCpu $b (Snap @{ 101 = @('svchost', 12.6); 102 = @('MsMpEng', 10.0); 4 = @('System', 10.0); 9001 = @('pwsh', 10.0) }) 10.0
    Test 'one_process_at_0.26_discards' ((Test-ForeignBusy $m) -and $m.max_process.name -eq 'svchost' -and $m.max_process.pid -eq 101) $m.max_process
    $m = Measure-ForeignCpu $b (Snap @{ 101 = @('svchost', 12.4); 102 = @('MsMpEng', 10.0); 4 = @('System', 10.0); 9001 = @('pwsh', 10.0) }) 10.0
    Test 'one_process_at_0.24_does_not' (-not (Test-ForeignBusy $m)) $m.max_process
    $m = Measure-ForeignCpu $b (Snap @{ 101 = @('svchost', 11.4); 102 = @('MsMpEng', 11.4); 4 = @('System', 10.0); 9001 = @('pwsh', 10.0) }) 10.0
    Test 'two_processes_at_0.14_do_not_discard' (-not (Test-ForeignBusy $m) -and [math]::Abs($m.aggregate_ratio - 0.28) -lt 1e-6 -and [math]::Abs($m.max_process_ratio - 0.14) -lt 1e-9) @{ agg = $m.aggregate_ratio; max = $m.max_process_ratio }
    Test 'aggregate_and_individual_distinguishable' ($m.aggregate_ratio -ge 0.25 -and $m.max_process_ratio -lt 0.25 -and $m.top.Count -eq 2)
    $m = Measure-ForeignCpu $b (Snap @{ 101 = @('svchost', 11.0); 102 = @('MsMpEng', 10.0); 4 = @('System', 99.0); 9001 = @('pwsh', 99.0)
            9002 = @('WmiPrvSE', 99.0); 9003 = @('conhost', 99.0); 9004 = @('Memory Compression', 99.0) }) 10.0 @(9001)
    Test 'harness_and_excluded_not_counted' (-not (Test-ForeignBusy $m) -and $m.max_process.name -eq 'svchost' -and $m.foreign_process_count -eq 1 -and $m.valid) @($m.top | ForEach-Object { $_.name })
    $m = Measure-ForeignCpu $b (Snap @{ 101 = @('MsMpEng', 3.0); 102 = @('MsMpEng', 10.0); 4 = @('System', 10.0) }) 10.0
    Test 'pid_reuse_new_name_counts_all_cpu' ((Test-ForeignBusy $m) -and $m.max_process.new_process -and $m.replaced_pids.Count -eq 1) $m.max_process
    $m = Measure-ForeignCpu $b (Snap @{ 101 = @('svchost', 13.0, (7 + 20000000)); 102 = @('MsMpEng', 10.0); 4 = @('System', 10.0) }) 10.0
    Test 'pid_reuse_new_start_time_counts_all_cpu' ((Test-ForeignBusy $m) -and [math]::Abs($m.max_process.cpu_s - 13.0) -lt 1e-9) $m.max_process
    $m = Measure-ForeignCpu $b (Snap @{ 101 = @('svchost', 3.0); 102 = @('MsMpEng', 10.0); 4 = @('System', 10.0) }) 10.0
    Test 'counter_going_backwards_counts_all_cpu' ((Test-ForeignBusy $m) -and $m.max_process.new_process) $m.max_process
    $m = Measure-ForeignCpu $b (Snap @{ 101 = @('svchost', $null); 102 = @('MsMpEng', 10.0); 4 = @('System', 10.0) }) 10.0
    Test 'missing_counter_fails_closed' ((Test-ForeignBusy $m) -and -not $m.valid -and $m.unreadable.Count -eq 1) $m.invalid_reason
    $m = Measure-ForeignCpu $b (Snap @{ 101 = @($null, 11.0); 102 = @('MsMpEng', 10.0) }) 10.0
    Test 'missing_name_fails_closed' ((Test-ForeignBusy $m) -and -not $m.valid) $m.invalid_reason
    $m = Measure-ForeignCpu (Snap @{ 101 = @('svchost', $null) }) (Snap @{ 101 = @('svchost', 10.1) }) 10.0
    Test 'missing_start_counter_fails_closed' ((Test-ForeignBusy $m) -and -not $m.valid) $m.invalid_reason
    $m = Measure-ForeignCpu @{} (Snap @{ 101 = @('svchost', 10.0) }) 10.0
    Test 'empty_snapshot_fails_closed' ((Test-ForeignBusy $m) -and -not $m.valid) $m.invalid_reason
    foreach ($w in 0.0, -1.0, [double]::NaN) {
        $m = Measure-ForeignCpu $b $b $w
        Test "invalid_wall_${w}_fails_closed" ((Test-ForeignBusy $m) -and -not $m.valid) $m.invalid_reason
    }
    $m = Measure-ForeignCpu $b (Snap @{ 102 = @('MsMpEng', 10.0); 4 = @('System', 10.0) }) 10.0
    Test 'exited_process_recorded' ((@($m.exited | ForEach-Object { $_.name } | Sort-Object) -join ',') -eq 'pwsh,svchost' -and $m.valid) $m.exited
    # Counters .NET cannot read (service processes for a standard user) are filled from Win32_Process, never guessed.
    $net = @{ 201 = @{ name = 'svchost'; cpu_s = $null; start = $null; source = 'dotnet' }; 202 = @{ name = $null; cpu_s = $null; start = $null; source = 'dotnet' }
        203 = @{ name = 'dwm'; cpu_s = $null; start = $null; source = 'dotnet' }; 204 = @{ name = 'gone'; cpu_s = $null; start = $null; source = 'dotnet' }
        205 = @{ name = 'pwsh'; cpu_s = 4.0; start = 50; source = 'dotnet' } }
    $created = [datetime]::new(2026, 11, 11, 21, 0, 0, [DateTimeKind]::Utc)
    $rows = @([pscustomobject]@{ ProcessId = 201; Name = 'svchost.exe'; KernelModeTime = 10000000; UserModeTime = 15000000; CreationDate = $created }
        [pscustomobject]@{ ProcessId = 202; Name = 'MsMpEng.exe'; KernelModeTime = 30000000; UserModeTime = 0; CreationDate = $created }
        [pscustomobject]@{ ProcessId = 203; Name = 'dwm.exe'; KernelModeTime = $null; UserModeTime = $null; CreationDate = $null }
        [pscustomobject]@{ ProcessId = 205; Name = 'pwsh.exe'; KernelModeTime = 999e7; UserModeTime = 0; CreationDate = $created })
    $mg = Merge-CpuSnapshot $net $rows
    Test 'wmi_fills_unreadable_cpu' ($mg[201].cpu_s -eq 2.5 -and $mg[201].name -eq 'svchost' -and $mg[201].source -eq 'wmi' -and $mg[201].start -eq $created.Ticks) $mg[201]
    Test 'wmi_fills_unreadable_name_without_extension' ($mg[202].name -eq 'MsMpEng' -and $mg[202].cpu_s -eq 3.0)
    Test 'wmi_without_times_stays_unreadable' ($mg.ContainsKey(203) -and $null -eq $mg[203].cpu_s)
    Test 'pid_gone_before_wmi_is_left_out' (-not $mg.ContainsKey(204))
    Test 'readable_dotnet_counter_kept' ($mg[205].cpu_s -eq 4.0 -and $mg[205].source -eq 'dotnet')
    $m = Measure-ForeignCpu (Snap @{ 1 = @('x', 0.0) }) $mg 10.0
    Test 'wmi_row_without_times_fails_closed' ((Test-ForeignBusy $m) -and -not $m.valid -and $m.unreadable[0].pid -eq 203) $m.unreadable
    $mg = Merge-CpuSnapshot $net @()
    $m = Measure-ForeignCpu (Snap @{ 1 = @('x', 0.0) }) $mg 10.0
    Test 'failed_wmi_query_fails_closed' ($mg.Count -eq 5 -and (Test-ForeignBusy $m) -and -not $m.valid -and $m.unreadable.Count -eq 4) $m.unreadable
    $m = Measure-ForeignCpu (Snap @{ 101 = @('svchost', 10.0, 1000) }) (Snap @{ 101 = @('svchost', 10.5, (1000 + 9999999)) }) 10.0
    Test 'start_time_precision_difference_is_same_process' (-not $m.max_process.new_process -and [math]::Abs($m.max_process.cpu_s - 0.5) -lt 1e-9) $m.max_process
    $m = Measure-ForeignCpu (Snap @{ 101 = @('svchost', 10.0, 1000) }) (Snap @{ 101 = @('svchost', 10.5, (1000 + 20000000)) }) 10.0
    Test 'start_time_two_seconds_apart_is_new_process' ($m.max_process.new_process -and (Test-ForeignBusy $m)) $m.max_process
    # The historical v2 solo measurements (run 43102297504, the recorded per-process CPU) stay discarded either way.
    $v2 = @(
        @{ name = 'deberta_solo_1'; wall = 44.0; cpu = @{ 6820 = @('svchost', 25.53); 2744 = @('WindowsTerminal', 2.5); 8020 = @('dwm', 0.09); 8208 = @('svchost', 0.06) } },
        @{ name = 'deberta_solo_1_repeat'; wall = 41.9; cpu = @{ 6820 = @('svchost', 12.03); 2744 = @('WindowsTerminal', 2.14); 8020 = @('dwm', 0.11); 9668 = @('SecurityHealthService', 0.11); 3932 = @('WindowsAzureGuestAgent', 0.06) } }
    )
    foreach ($h in $v2) {
        $zero = @{}; foreach ($k in $h.cpu.Keys) { $zero[$k] = @($h.cpu[$k][0], 0.0) }
        $m = Measure-ForeignCpu (Snap $zero) (Snap $h.cpu) $h.wall
        Test "historical_$($h.name)_discarded_per_process" ((Test-ForeignBusy $m) -and $m.max_process.pid -eq 6820) @{ max = $m.max_process_ratio; agg = $m.aggregate_ratio }
        Test "historical_$($h.name)_discarded_aggregate" ($m.aggregate_ratio -ge 0.25) $m.aggregate_ratio
    }

    # --- 7. v3 §3 idle settling on synthetic snapshots and a simulated clock ----------------------------------------
    $q = 0.5   # 0.05 CPU-s per wall-s over a 10 s window
    $st = Settle (Window-Source @($q, $q, $q))
    Test 'settle_three_quiet_windows' ($st.settled -and $st.windows.Count -eq 3 -and $st.attempt_s -eq 30.0) @{ n = $st.windows.Count; s = $st.attempt_s; reason = $st.reason }
    Test 'settle_windows_contiguous_nonoverlapping' ((@($st.windows | ForEach-Object { $_.start_s }) -join ',') -eq '0,10,20' -and -not ($st.windows | Where-Object { $_.duration_s -ne 10.0 }))
    Test 'settle_windows_record_top_and_max' (-not ($st.windows | Where-Object { -not $_.Contains('top') -or $null -eq $_.max_process -or $_.max_process.name -ne 'WindowsTerminal' }))
    $st = Settle (Window-Source @($q, $q, 3.0, $q, $q, $q))
    Test 'settle_noisy_window_resets_count' ($st.settled -and $st.windows.Count -eq 6 -and (@($st.windows | ForEach-Object { $_.consecutive_quiet }) -join ',') -eq '1,2,0,1,2,3') @($st.windows | ForEach-Object { $_.consecutive_quiet })
    $st = Settle (Window-Source @($q, 3.0, $q, 3.0, $q, 3.0, $q, 3.0, $q, 3.0, $q, 3.0, $q, 3.0, $q, 3.0, $q, 3.0))
    Test 'settle_separated_quiet_windows_never_combine' (-not $st.settled -and -not ($st.windows | Where-Object { $_.consecutive_quiet -gt 1 }) -and $st.reason -like 'attempt budget*') @{ reason = $st.reason; n = $st.windows.Count }
    $st = Settle (Window-Source @(2.0, 2.0, 2.0))
    Test 'settle_process_at_0.20_prevents' (-not $st.settled -and -not ($st.windows | Where-Object { $_.quiet })) $st.reason
    $st = Settle (Window-Source @(1.99, 1.99, 1.99))
    Test 'settle_process_just_under_0.20_permits' ($st.settled -and $st.windows.Count -eq 3) $st.reason
    $st = Settle (Window-Source @(2.2, 2.2, 2.2))
    $m22 = Measure-ForeignCpu (Snap @{ 1 = @('svchost', 0.0) }) (Snap @{ 1 = @('svchost', 2.2) }) 10.0
    Test 'screen_0.20_does_not_replace_rule_0.25' (-not $st.settled -and -not (Test-ForeignBusy $m22) -and $NoiseForeignCpuRatio -eq 0.25 -and $SettleQuietRatio -eq 0.20) @{ settled = $st.settled; busy = (Test-ForeignBusy $m22) }
    $st = Settle (Window-Source @(5.0))
    Test 'settle_attempt_budget_180' (-not $st.settled -and $st.reason -like 'attempt budget*' -and $st.attempt_s -le 180.0 -and $st.windows.Count -eq 18) @{ s = $st.attempt_s; n = $st.windows.Count }
    $bud = @{ total_s = 600.0; used_s = 0.0 }
    $runs = foreach ($i in 1..5) { Settle (Window-Source @(5.0)) $bud }
    Test 'settle_run_budget_600' (((@($runs | ForEach-Object { $_.attempt_s })) -join ',') -eq '180,180,180,60,0' -and $bud.used_s -le 600.0 -and $runs[3].reason -like 'run budget*' -and $runs[4].windows.Count -eq 0) @{ s = @($runs | ForEach-Object { $_.attempt_s }); used = $bud.used_s }
    $bud = @{ total_s = 600.0; used_s = 575.0 }
    $st = Settle (Window-Source @($q, $q, $q)) $bud
    Test 'settle_run_budget_blocks_quiet_wait' (-not $st.settled -and $st.windows.Count -eq 2 -and $bud.used_s -le 600.0 -and $st.reason -like 'run budget*') @{ n = $st.windows.Count; used = $bud.used_s }
    $st = Settle { @{ 6820 = @{ name = 'svchost'; cpu_s = $null; start = 11 } } }
    Test 'settle_unreadable_counter_never_quiet' (-not $st.settled -and -not ($st.windows | Where-Object { $_.quiet -or $_.valid })) $st.reason
    $st = Settle { throw 'process enumeration failed' }
    Test 'settle_snapshot_failure_fails_closed' (-not $st.settled -and $st.reason -like 'settling measurement failed*') $st.reason
    $script:Now = 0.0
    $st = Wait-IdleSettled -Budget @{ total_s = 600.0; used_s = 0.0 } -Snapshot (Window-Source @($q, $q, $q)) -Clock $script:Clock -Sleep { param($s) $script:Now -= 1.0 }
    Test 'settle_clock_backwards_fails_closed' (-not $st.settled -and $st.windows.Count -eq 1 -and $st.reason -like 'clock*') $st.reason
    $st = Wait-IdleSettled -Budget @{ total_s = 600.0; used_s = 0.0 } -Snapshot (Window-Source @($q, $q, $q)) -Clock $script:Clock -Sleep { param($s) }
    Test 'settle_clock_not_advancing_fails_closed' (-not $st.settled -and $st.reason -like 'clock*') $st.reason
    $st = Wait-IdleSettled -Budget @{ total_s = 600.0; used_s = 0.0 } -Snapshot (Window-Source @($q, $q, $q)) -Clock { [double]::NaN } -Sleep $script:SleepFor
    Test 'settle_invalid_clock_fails_closed' (-not $st.settled -and $st.reason -like 'settling measurement failed*') $st.reason
    Test 'settle_constants_as_predeclared' ($SettleQuietRatio -eq 0.20 -and $SettleWindowSec -eq 10.0 -and $SettleWindows -eq 3 -and $SettleAttemptSec -eq 180.0 -and $SettleTotalSec -eq 600.0 -and $NoiseForeignCpuRatio -eq 0.25)

    # --- 8. settling inside Measure-Condition never counts, never adds attempts ------------------------------------
    # A programmable Invoke-Phase: records each call and files a process record whose busiest foreign process has the
    # ratio the test chooses. The driver's own Measure-Condition decides everything else.
    $script:Calls = [System.Collections.Generic.List[string]]::new()
    $script:Ratios = @{}
    function Invoke-Phase([string]$Stage, [string]$Phase, [bool]$Offline, [int]$TimeoutSec, [string[]]$Extra = @(), [bool]$Measure = $false, [string]$Name = $Stage) {
        $script:Calls.Add($Name)
        $ratio = if ($script:Ratios.ContainsKey($Name)) { $script:Ratios[$Name] } else { 0.01 }
        $Processes[$Name] = [ordered]@{ min_available_phys_gib = 12.0; foreign_cpu_ratio = $ratio; foreign_cpu_max_process_ratio = $ratio
            foreign_cpu_max_process = @{ pid = 6820; name = 'svchost'; ratio = $ratio }; foreign_measurement_valid = $true }
        return @{ data = @{ resource_policy = @{ reserve_mb = 818 } } }
    }
    function Run-Solo([scriptblock]$SnapshotFn) {
        Reset-State; $script:Calls.Clear()
        Set-Item -Path function:Cpu-Snapshot -Value $SnapshotFn
        Measure-Condition 'deberta_solo' 'deberta' 'solo' 3 6>$null
    }
    $quietSnap = { $script:Snap++; @{ 7 = @{ name = 'svchost'; cpu_s = 0.01 * $script:Snap; start = 1 } } }
    $script:Ratios = @{ deberta_solo_1 = 0.30; deberta_solo_1_repeat = 0.26 }
    Run-Solo $quietSnap
    Test 'settled_then_busy_is_discarded' ((@($Discarded['deberta_solo']) -join ',') -eq 'deberta_solo_1,deberta_solo_1_repeat' -and $Counted.Count -eq 0) @($Discarded['deberta_solo'])
    Test 'two_discards_still_stop_condition' (@($Checks | Where-Object { $_.id -eq 'deberta_solo_slot1_two_discards' -and -not $_.ok -and $_.kind -eq 'infrastructure' }).Count -eq 1 -and (@($script:Calls) -join ',') -eq 'deberta_solo_1,deberta_solo_1_repeat') @($script:Calls)
    Test 'repeat_also_settled_first' ((@($Settling.Keys) -join ',') -eq 'deberta_solo_1,deberta_solo_1_repeat' -and $Settling['deberta_solo_1_repeat'].settled) @($Settling.Keys)
    Test 'discard_records_individual_rule' ($Processes['deberta_solo_1'].noise.foreign_busy -and $Processes['deberta_solo_1'].noise.foreign_max_process.name -eq 'svchost' -and $Processes['deberta_solo_1'].noise.idle_settled_before)
    $script:Ratios = @{ deberta_solo_2 = 0.40 }
    Run-Solo $quietSnap
    Test 'one_discard_one_repeat_then_continue' ((@($script:Calls) -join ',') -eq 'deberta_solo_1,deberta_solo_2,deberta_solo_2_repeat,deberta_solo_3' -and (@($Counted.Keys) -join ',') -eq 'deberta_solo_1,deberta_solo_2_repeat,deberta_solo_3') @($script:Calls)
    $script:Ratios = @{}
    $noisySnap = { $script:Snap++; @{ 7 = @{ name = 'svchost'; cpu_s = 5.0 * $script:Snap; start = 1 } } }
    Run-Solo $noisySnap
    $fail = @($Checks | Where-Object { -not $_.ok })
    Test 'settling_timeout_is_inconclusive' ($fail.Count -eq 1 -and $fail[0].id -eq 'deberta_solo_1_idle_settled' -and $fail[0].kind -eq 'infrastructure' -and $fail[0].detail -like 'attempt budget*') @($fail | ForEach-Object { "$($_.id) [$($_.kind)] $($_.detail)" })
    Test 'settling_timeout_measures_nothing' ($script:Calls.Count -eq 0 -and $Counted.Count -eq 0 -and $Discarded['deberta_solo'].Count -eq 0) @($script:Calls)
    Test 'settling_record_written_on_timeout' (Test-Path -LiteralPath (Join-Path $Out 'deberta_solo_1.settling.json'))
    $script:Ratios = @{ deberta_solo_1 = 0.30 }
    # quiet until the first measured process has run, then busy: the repeat cannot settle, and nothing replaces it
    $script:CpuAcc = 0.0
    $flipSnap = { $script:CpuAcc += $(if ($script:Calls.Count -ge 1) { 5.0 } else { 0.01 }); @{ 7 = @{ name = 'svchost'; cpu_s = $script:CpuAcc; start = 1 } } }
    Run-Solo $flipSnap
    Test 'no_extra_attempt_after_settling_fails_on_repeat' ((@($script:Calls) -join ',') -eq 'deberta_solo_1' -and @($Checks | Where-Object { $_.id -eq 'deberta_solo_1_repeat_idle_settled' -and -not $_.ok }).Count -eq 1 -and $Counted.Count -eq 0) @($script:Calls)
    Reset-State; $script:Calls.Clear(); $script:Ratios = @{}
    $script:Worker = [pscustomobject]@{ Id = 4242 }
    Measure-Condition 'deberta_concurrent' 'deberta' 'concurrent' 3 6>$null
    Test 'concurrent_protocol_has_no_settling' ($Settling.Count -eq 0 -and $script:SettleBudget.used_s -eq 0.0 -and $Counted.Count -eq 3) @($Settling.Keys)
    $script:Worker = $null
}
finally {
    Remove-Item -LiteralPath $Out -Recurse -Force -ErrorAction SilentlyContinue
}

$failed = @($Results | Where-Object { -not $_.ok })
foreach ($t in $Results) { "{0} {1} {2}" -f $(if ($t.ok) { 'PASS' } else { 'FAIL' }), $t.id, $(if ($t.ok) { '' } else { ($t.detail | ConvertTo-Json -Compress -Depth 4) }) }
"`n$($Results.Count - $failed.Count)/$($Results.Count) driver self-test checks passed"
exit $(if ($failed.Count) { 1 } else { 0 })
