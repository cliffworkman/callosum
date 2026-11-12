# P1b foreign-CPU accounting and the V3 idle-settling check (inc 639; P1B_PREDECLARATION_V3.md §§3-4).
#
# Pure functions, dot-sourced by p1b_qualify.ps1 and p1b_driver_selftest.ps1. Nothing here reads a process, a clock
# or sleeps: the driver passes CPU snapshots in, and Wait-IdleSettled receives its snapshot, clock and sleep as script
# blocks, so the self-test can drive it with synthetic snapshots and a simulated clock.
#
# A snapshot is a hashtable keyed by PID; each value is @{ name = <string or $null>; cpu_s = <double or $null>;
# start = <UTC ticks or $null>; source = 'dotnet' | 'wmi' }. $null means the counter could not be read.

# v1 §7: the harness and the kernel pseudo-processes. The measured process, its children, the driver and the Arctic
# worker are excluded by PID by the caller.
$NoiseExcludedNames = @('Idle', 'System', 'Registry', 'Memory Compression', 'Secure System', 'WmiPrvSE', 'conhost')
$NoiseForeignCpuRatio = 0.25    # v1 §7 post-measurement discard, per individual foreign process (unchanged)
$SettleQuietRatio = 0.20        # v3 §3 pre-measurement screen, per individual foreign process
$SettleWindowSec = 10.0         # v3 §3
$SettleWindows = 3              # v3 §3: consecutive quiet windows
$SettleAttemptSec = 180.0       # v3 §3: per settling attempt
$SettleTotalSec = 600.0         # v3 §3: whole hosted run
$SameStartToleranceTicks = 10000000   # 1 s: .NET and WMI report a process's start time at different precision

# v3 §2: fill the counters .NET could not read from Win32_Process (KernelModeTime + UserModeTime, 100 ns units; the
# WMI provider runs as SYSTEM). A PID missing from the WMI rows exited between the two reads and is left out of the
# snapshot, so it appears as exited; a WMI row without times, or no WMI rows at all, keeps $null, which
# Measure-ForeignCpu fails closed on.
function Merge-CpuSnapshot([hashtable]$Snapshot, $WmiRows) {
    $rows = @{}
    foreach ($w in @($WmiRows)) { if ($null -ne $w) { $rows[[int]$w.ProcessId] = $w } }
    if ($rows.Count -eq 0) { return $Snapshot }   # the WMI query failed: keep every $null, never treat it as an exit
    $out = @{}
    foreach ($id in $Snapshot.Keys) {
        $e = $Snapshot[$id]
        if ($null -ne $e.name -and $null -ne $e.cpu_s) { $out[$id] = $e; continue }
        if (-not $rows.ContainsKey([int]$id)) { continue }
        $w = $rows[[int]$id]
        $name = if ($null -ne $e.name) { $e.name } elseif ($w.Name) { [System.IO.Path]::GetFileNameWithoutExtension([string]$w.Name) } else { $null }
        $cpu = if ($null -ne $w.KernelModeTime -and $null -ne $w.UserModeTime) { ([double]$w.KernelModeTime + [double]$w.UserModeTime) / 1e7 } else { $null }
        $start = if ($null -ne $e.start) { $e.start } elseif ($w.CreationDate -is [datetime]) { $w.CreationDate.ToUniversalTime().Ticks } else { $null }
        $out[$id] = @{ name = $name; cpu_s = $cpu; start = $start; source = 'wmi' }
    }
    return $out
}

# Foreign CPU between two snapshots. Every surviving foreign process is judged on its own CPU; the aggregate is kept
# only as a diagnostic. Fails closed: a foreign process whose counters cannot be read, a non-positive or non-finite
# wall time, or an empty snapshot make the measurement invalid, never quiet.
function Measure-ForeignCpu {
    param([hashtable]$Before, [hashtable]$After, [double]$WallSeconds, [int[]]$ExcludePids = @(), [string[]]$ExcludeNames = $NoiseExcludedNames)
    $procs = [System.Collections.Generic.List[object]]::new()
    $unreadable = [System.Collections.Generic.List[object]]::new()
    $replaced = [System.Collections.Generic.List[object]]::new()
    $exited = [System.Collections.Generic.List[object]]::new()
    $reasons = [System.Collections.Generic.List[string]]::new()
    if ($null -eq $Before -or $Before.Count -eq 0) { $reasons.Add('empty start snapshot') }
    if ($null -eq $After -or $After.Count -eq 0) { $reasons.Add('empty end snapshot') }
    if ([double]::IsNaN($WallSeconds) -or [double]::IsInfinity($WallSeconds) -or $WallSeconds -le 0) { $reasons.Add("invalid wall time $WallSeconds") }
    $wall = if ($reasons.Count) { 1.0 } else { $WallSeconds }
    $total = 0.0
    if ($After) {
        foreach ($id in $After.Keys) {
            $a = $After[$id]
            if ($ExcludePids -contains $id) { continue }
            if ($null -ne $a.name -and $ExcludeNames -contains $a.name) { continue }
            if ($null -eq $a.name -or $null -eq $a.cpu_s) { $unreadable.Add([ordered]@{ pid = $id; name = $a.name; at = 'end' }); continue }
            $b = if ($Before -and $Before.ContainsKey($id)) { $Before[$id] } else { $null }
            # The same process only if the PID, the name and (when both are known) the start time agree. Anything else
            # is a new process, all of whose CPU time is counted: over-counting can only discard, never pass.
            $same = $null -ne $b -and $b.name -ceq $a.name -and ($null -eq $b.start -or $null -eq $a.start -or [math]::Abs([double]$b.start - [double]$a.start) -le $SameStartToleranceTicks)
            if ($same -and $null -eq $b.cpu_s) { $unreadable.Add([ordered]@{ pid = $id; name = $a.name; at = 'start' }); continue }
            $d = if ($same) { [double]$a.cpu_s - [double]$b.cpu_s } else { [double]$a.cpu_s }
            if ($same -and $d -lt 0) { $same = $false; $d = [double]$a.cpu_s }   # counter went backwards: an undetected PID reuse
            if (-not $same -and $null -ne $b) { $replaced.Add([ordered]@{ pid = $id; before = $b.name; after = $a.name }) }
            if ($d -le 0) { continue }
            $total += $d
            $procs.Add([pscustomobject]@{ pid = $id; name = $a.name; cpu_s = $d; ratio = $d / $wall; new_process = -not $same })
        }
    }
    if ($Before) {
        foreach ($id in $Before.Keys) {
            $b = $Before[$id]
            if ($After -and $After.ContainsKey($id)) { continue }
            if ($ExcludePids -contains $id -or ($null -ne $b.name -and $ExcludeNames -contains $b.name)) { continue }
            $exited.Add([ordered]@{ pid = $id; name = $b.name })   # its CPU after the start snapshot is not observable
        }
    }
    if ($unreadable.Count) { $reasons.Add("$($unreadable.Count) foreign process counter(s) unreadable") }
    $sorted = @($procs | Sort-Object -Property cpu_s -Descending)
    $max = if ($sorted.Count) { $sorted[0] } else { $null }
    $round = { param($p) [ordered]@{ pid = $p.pid; name = $p.name; cpu_s = [math]::Round($p.cpu_s, 3); ratio = [math]::Round($p.ratio, 4); new_process = $p.new_process } }
    return [ordered]@{
        valid = ($reasons.Count -eq 0); invalid_reason = @($reasons)
        wall_s = [math]::Round($WallSeconds, 3)
        max_process = $(if ($max) { & $round $max } else { $null })
        max_process_ratio = $(if ($max) { [double]$max.ratio } else { 0.0 })   # unrounded: the value the rules compare
        aggregate_cpu_s = [math]::Round($total, 3); aggregate_ratio = [math]::Round($total / $wall, 4)   # diagnostic only
        top = @($sorted | Select-Object -First 5 | ForEach-Object { & $round $_ })
        foreign_process_count = $sorted.Count
        unreadable = @($unreadable); replaced_pids = @($replaced); exited = @($exited)
    }
}

# v1 §7 post-measurement rule: discarded when the measurement is invalid or any single foreign process used at least
# $Threshold CPU-seconds per wall-second.
function Test-ForeignBusy($Measurement, [double]$Threshold = $NoiseForeignCpuRatio) {
    return (-not $Measurement.valid) -or ([double]$Measurement.max_process_ratio -ge $Threshold)
}

# v3 §3: untimed idle settling before one solo measured process. Contiguous, non-overlapping windows of $WindowSec,
# each quiet when its measurement is valid, lasts at least $WindowSec on the monotonic clock and no single foreign
# process reaches $QuietRatio. Succeeds on $Windows consecutive quiet windows; a noisy or invalid window resets the
# count. Bounded by $AttemptSec for this attempt and by the shared $Budget (@{ total_s; used_s }) for the run. Never
# kills, suspends or reprioritises anything. Returns the full record; settling never counts or accepts a measurement.
function Wait-IdleSettled {
    param([Parameter(Mandatory)][hashtable]$Budget, [Parameter(Mandatory)][scriptblock]$Snapshot, [Parameter(Mandatory)][scriptblock]$Clock,
        [Parameter(Mandatory)][scriptblock]$Sleep, [int[]]$ExcludePids = @(), [string[]]$ExcludeNames = $NoiseExcludedNames,
        [double]$WindowSec = $SettleWindowSec, [int]$Windows = $SettleWindows, [double]$QuietRatio = $SettleQuietRatio, [double]$AttemptSec = $SettleAttemptSec)
    $rec = [ordered]@{ settled = $false; reason = $null; quiet_ratio = $QuietRatio; window_s = $WindowSec; windows_required = $Windows
        attempt_budget_s = $AttemptSec; run_budget_s = [double]$Budget.total_s; run_used_before_s = [math]::Round([double]$Budget.used_s, 3)
        attempt_s = $null; run_used_after_s = $null; windows = [System.Collections.Generic.List[object]]::new()
    }
    $t0 = $null; $last = $null
    try {
        $t0 = [double](& $Clock); $last = $t0
        if ([double]::IsNaN($t0) -or [double]::IsInfinity($t0)) { throw "invalid clock reading $t0" }
        $consecutive = 0
        $s0 = & $Snapshot; $w0 = [double](& $Clock); $last = $w0
        while ($true) {
            $elapsed = $w0 - $t0
            if ($elapsed + $WindowSec -gt $AttemptSec) { $rec.reason = "attempt budget: another $WindowSec s window would pass $AttemptSec s"; break }
            if ([double]$Budget.used_s + $elapsed + $WindowSec -gt [double]$Budget.total_s) { $rec.reason = "run budget: another $WindowSec s window would pass $($Budget.total_s) s"; break }
            & $Sleep $WindowSec
            $s1 = & $Snapshot; $w1 = [double](& $Clock); $last = $w1
            $d = $w1 - $w0
            $m = Measure-ForeignCpu $s0 $s1 $d $ExcludePids $ExcludeNames
            $long = $d -ge $WindowSec
            $quiet = $m.valid -and $long -and ($m.max_process_ratio -lt $QuietRatio)
            $consecutive = if ($quiet) { $consecutive + 1 } else { 0 }
            $rec.windows.Add([ordered]@{ index = $rec.windows.Count + 1; start_s = [math]::Round($w0 - $t0, 3); duration_s = [math]::Round($d, 3)
                    quiet = $quiet; consecutive_quiet = $consecutive; full_length = $long; valid = $m.valid; invalid_reason = $m.invalid_reason
                    max_process = $m.max_process; aggregate_cpu_s = $m.aggregate_cpu_s; aggregate_ratio = $m.aggregate_ratio; top = $m.top
                    unreadable = $m.unreadable; replaced_pids = $m.replaced_pids; exited = @($m.exited | ForEach-Object { $_.name })
                })
            $s0 = $s1; $w0 = $w1
            # A window shorter than $WindowSec means the sleep or the monotonic clock failed; stop rather than loop.
            if (-not $long) { $rec.reason = "clock: window $($rec.windows.Count) lasted $([math]::Round($d, 3)) s, under $WindowSec s"; break }
            if (($w1 - $t0) -gt $AttemptSec) { $rec.reason = "attempt budget: $([math]::Round($w1 - $t0, 3)) s passed $AttemptSec s"; break }
            if ([double]$Budget.used_s + ($w1 - $t0) -gt [double]$Budget.total_s) { $rec.reason = "run budget: $($Budget.total_s) s exceeded"; break }
            if ($consecutive -ge $Windows) { $rec.settled = $true; break }
        }
    }
    catch { $rec.settled = $false; $rec.reason = "settling measurement failed: $($_.Exception.Message)" }
    $spent = if ($null -ne $t0 -and $null -ne $last -and $last -ge $t0) { $last - $t0 } else { 0.0 }
    $Budget.used_s = [double]$Budget.used_s + $spent
    $rec.attempt_s = [math]::Round($spent, 3); $rec.run_used_after_s = [math]::Round([double]$Budget.used_s, 3)
    return $rec
}
