# Canonical Callosum runtime tree digest (mirror of python_runtime.rs filesystem_entries + tree_digest, Windows branch).
# - every regular file under the root, recursively; directories contribute nothing
# - a reparse point (symlink/junction) anywhere fails closed, as the Rust code does on Windows
# - relative path with '/' separators; entries sorted by the UTF-8 bytes of that path (Rust String Ord)
# - line = "file\t<relative>\t<size>\t<lowercase sha256>\t<0|1>\n", executable = extension in exe/com/bat/cmd
# - digest = sha256("callosum-python-runtime-tree-v1\n" + all lines)
# Exclusion: the top-level runtime-install.json, which write_receipt adds AFTER the digest is checked.
# Read-only: opens files for reading only.
# -ExcludeList (diagnostic only, never for acceptance): file of relative paths to leave out, one per line.
param([Parameter(Mandatory)][string]$Root, [string]$ListOut, [string]$ExcludeList)
$ErrorActionPreference = 'Stop'
$rootFull = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
$exclude = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
if ($ExcludeList) { foreach ($l in [IO.File]::ReadAllLines($ExcludeList)) { if ($l) { [void]$exclude.Add($l) } } }
$utf8 = New-Object System.Text.UTF8Encoding($false)
$sha = [System.Security.Cryptography.SHA256]::Create()
$items = Get-ChildItem -LiteralPath $rootFull -Recurse -Force
$entries = New-Object System.Collections.Generic.List[object]
foreach ($i in $items) {
    if ($i.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "REPARSE POINT IN RUNTIME TREE: $($i.FullName)" }
    if ($i.PSIsContainer) { continue }
    $rel = $i.FullName.Substring($rootFull.Length + 1).Replace('\', '/')
    if ($rel -ceq 'runtime-install.json') { continue }
    if ($exclude.Contains($rel)) { continue }
    $ext = $i.Extension.TrimStart('.').ToLowerInvariant()
    $s = [IO.File]::OpenRead($i.FullName)
    try { $h = -join ($sha.ComputeHash($s) | ForEach-Object { $_.ToString('x2') }) } finally { $s.Dispose() }
    $entries.Add([pscustomobject]@{ Rel = $rel; Key = [BitConverter]::ToString($utf8.GetBytes($rel)); Bytes = $utf8.GetBytes($rel); Size = $i.Length; Hash = $h; Exec = [int]($ext -in 'exe','com','bat','cmd') })
}
$cmp = [Comparison[object]] {
    param($a, $b)
    $x = $a.Bytes; $y = $b.Bytes; $n = [Math]::Min($x.Length, $y.Length)
    for ($k = 0; $k -lt $n; $k++) { if ($x[$k] -ne $y[$k]) { return $x[$k].CompareTo($y[$k]) } }
    return $x.Length.CompareTo($y.Length)
}
$entries.Sort($cmp)
$ms = New-Object IO.MemoryStream
$dom = $utf8.GetBytes("callosum-python-runtime-tree-v1`n"); $ms.Write($dom, 0, $dom.Length)
$lines = New-Object System.Collections.Generic.List[string]
foreach ($e in $entries) {
    $line = "file`t$($e.Rel)`t$($e.Size)`t$($e.Hash)`t$($e.Exec)`n"
    $b = $utf8.GetBytes($line); $ms.Write($b, 0, $b.Length); $lines.Add($line.TrimEnd("`n"))
}
$digest = -join ($sha.ComputeHash($ms.ToArray()) | ForEach-Object { $_.ToString('x2') })
if ($ListOut) { [IO.File]::WriteAllLines($ListOut, $lines, $utf8) }
$bytes = ($entries | Measure-Object Size -Sum).Sum
"entries $($entries.Count) bytes $bytes digest $digest"
