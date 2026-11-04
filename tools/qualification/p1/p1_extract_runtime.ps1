# Inc 632B-R: extract a Callosum runtime archive under the rules of python_runtime.rs extract_verified (Windows),
# using .NET System.Formats.Tar only (no Python, nothing extracted is executed).
# Mirrors Rust exactly:
#   - first path component must be "python-runtime"; every later component must be a normal component
#   - the root entry itself is skipped; duplicate relative paths fail
#   - directories are created; symlinks fail (Windows); any non-regular-file type fails
#   - file count checked against entry_count before each file; running byte total bounded by unpacked_bytes
#   - files created with CreateNew; bytes copied must equal header size; sha256 computed while writing
#   - executable = header mode & 0o111; final sort by UTF-8 bytes; digest = sha256(domain + lines)
#   - final check: entry count, unpacked bytes and tree digest must equal the manifest
# Stricter than Rust (fail closed, reported): empty/"."/".." components, backslash, colon, control or
# Windows-invalid characters, reserved device names, trailing dot/space, case-insensitive collisions,
# destination outside the root, a non-empty destination.
param(
    [Parameter(Mandatory)][string]$Archive,
    [Parameter(Mandatory)][string]$Dest,
    [Parameter(Mandatory)][string]$ManifestPath,
    [Parameter(Mandatory)][string]$ListOut
)
$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
[uint64]$maxEntries = 150000; [uint64]$maxUnpacked = 8GB
function Fail([string]$why) { throw "INVALID ARCHIVE: $why" }

if (Test-Path -LiteralPath $Dest) {
    if (Get-ChildItem -LiteralPath $Dest -Force | Select-Object -First 1) { Fail "destination not empty: $Dest" }
} else { New-Item -ItemType Directory -Path $Dest | Out-Null }
$root = (Resolve-Path -LiteralPath $Dest).Path.TrimEnd('\')
$rootPrefix = $root + '\'

$reserved = '^(CON|PRN|AUX|NUL|COM[0-9¹²³]|LPT[0-9¹²³])$'
$invalidChars = [char[]]((0..31 | ForEach-Object { [char]$_ }) + [char[]]'<>"|?*:\')
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)
$exact = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
$folded = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$entries = New-Object System.Collections.Generic.List[object]
[uint64]$unpacked = 0
$execMask = [IO.UnixFileMode]::UserExecute -bor [IO.UnixFileMode]::GroupExecute -bor [IO.UnixFileMode]::OtherExecute
$typeCounts = @{}

$fs = [IO.File]::OpenRead($Archive)
$gz = New-Object IO.Compression.GZipStream($fs, [IO.Compression.CompressionMode]::Decompress)
$reader = New-Object System.Formats.Tar.TarReader($gz, $false)
try {
    while ($null -ne ($e = $reader.GetNextEntry($false))) {
        $t = $e.EntryType.ToString(); $typeCounts[$t] = 1 + [int]$typeCounts[$t]
        $name = $e.Name
        $isDir = $e.EntryType -eq [System.Formats.Tar.TarEntryType]::Directory
        $trimmed = if ($isDir) { $name.TrimEnd('/') } else { $name }
        $parts = $trimmed.Split('/')
        if ($parts[0] -cne 'python-runtime') { Fail "wrong root: $name" }
        $relParts = $parts[1..($parts.Length - 1)]
        if ($parts.Length -eq 1) { $relParts = @() }
        foreach ($p in $relParts) {
            if ($p -eq '' -or $p -eq '.' -or $p -eq '..') { Fail "non-normal component: $name" }
            if ($p.IndexOfAny($invalidChars) -ge 0) { Fail "invalid character: $name" }
            if ($p.EndsWith('.') -or $p.EndsWith(' ')) { Fail "trailing dot/space: $name" }
            if (($p.Split('.')[0]) -match $reserved) { Fail "reserved device name: $name" }
        }
        if ($relParts.Count -eq 0) { continue }   # the root entry itself
        $rel = $relParts -join '/'
        if (-not $exact.Add($rel)) { Fail "duplicate path: $rel" }
        if (-not $folded.Add($rel)) { Fail "case-insensitive collision: $rel" }
        $destination = [IO.Path]::GetFullPath((Join-Path $root ($relParts -join '\')))
        if (-not $destination.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) { Fail "outside destination: $rel" }
        if ($isDir) { [void][IO.Directory]::CreateDirectory($destination); continue }
        if ([uint64]$entries.Count -ge [uint64]$manifest.entry_count -or [uint64]$entries.Count -ge $maxEntries) { Fail "too many entries" }
        if ($e.EntryType -eq [System.Formats.Tar.TarEntryType]::SymbolicLink) { Fail "symlink on Windows: $rel" }
        if ($e.EntryType -ne [System.Formats.Tar.TarEntryType]::RegularFile -and $e.EntryType -ne [System.Formats.Tar.TarEntryType]::V7RegularFile) { Fail "unsupported type $t : $rel" }
        [uint64]$size = $e.Length
        $unpacked += $size
        if ($unpacked -gt [uint64]$manifest.unpacked_bytes -or $unpacked -gt $maxUnpacked) { Fail "unpacked bytes exceed manifest" }
        $parent = [IO.Path]::GetDirectoryName($destination)
        [void][IO.Directory]::CreateDirectory($parent)
        foreach ($chk in @($parent)) { if ((Get-Item -LiteralPath $chk -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { Fail "reparse point parent: $rel" } }
        $out = New-Object IO.FileStream($destination, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $sha = [System.Security.Cryptography.IncrementalHash]::CreateHash([System.Security.Cryptography.HashAlgorithmName]::SHA256)
        [uint64]$copied = 0
        try {
            if ($null -ne $e.DataStream) {
                $buf = New-Object byte[] 1048576
                while (($n = $e.DataStream.Read($buf, 0, $buf.Length)) -gt 0) { $out.Write($buf, 0, $n); $sha.AppendData($buf, 0, $n); $copied += $n }
            }
        } finally { $out.Dispose() }
        if ($copied -ne $size) { Fail "short copy: $rel" }
        $hash = [Convert]::ToHexString($sha.GetHashAndReset()).ToLowerInvariant(); $sha.Dispose()
        $exec = [int](([int]$e.Mode -band [int]$execMask) -ne 0)
        $entries.Add([pscustomobject]@{ Rel = $rel; Bytes = $utf8.GetBytes($rel); Size = $size; Hash = $hash; Exec = $exec })
    }
} finally { $reader.Dispose(); $gz.Dispose(); $fs.Dispose() }

$cmp = [Comparison[object]] {
    param($a, $b)
    $x = $a.Bytes; $y = $b.Bytes; $n = [Math]::Min($x.Length, $y.Length)
    for ($k = 0; $k -lt $n; $k++) { if ($x[$k] -ne $y[$k]) { return $x[$k].CompareTo($y[$k]) } }
    return $x.Length.CompareTo($y.Length)
}
$entries.Sort($cmp)
$tree = [System.Security.Cryptography.IncrementalHash]::CreateHash([System.Security.Cryptography.HashAlgorithmName]::SHA256)
$tree.AppendData($utf8.GetBytes("callosum-python-runtime-tree-v1`n"))
$lines = New-Object System.Collections.Generic.List[string]
foreach ($x in $entries) {
    $line = "file`t$($x.Rel)`t$($x.Size)`t$($x.Hash)`t$($x.Exec)"
    $tree.AppendData($utf8.GetBytes($line + "`n")); $lines.Add($line)
}
$digest = [Convert]::ToHexString($tree.GetHashAndReset()).ToLowerInvariant()
[IO.File]::WriteAllLines($ListOut, $lines, (New-Object System.Text.UTF8Encoding($false)))
"tar entry types: " + (($typeCounts.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')
"executable entries: $(($entries | Where-Object Exec -eq 1).Count)"
"extract-stream entries $($entries.Count) bytes $unpacked digest $digest"
$ok = ([uint64]$entries.Count -eq [uint64]$manifest.entry_count) -and ($unpacked -eq [uint64]$manifest.unpacked_bytes) -and ($digest -ceq $manifest.tree_sha256)
if ($ok) { "EXTRACT-STREAM TREE MATCH" } else { "EXTRACT-STREAM TREE MISMATCH"; exit 1 }
