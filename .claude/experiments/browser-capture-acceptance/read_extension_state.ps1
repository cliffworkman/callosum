param(
    [Parameter(Mandatory=$true)][int]$CdpPort,
    [string]$ExtensionUrlFragment = "background.js"
)
# Reads the real extension's globally-set badge text / title via its own service worker's CDP
# debugger session -- proven mechanism (see click_extension.ps1's header comment for how this was
# verified against a throwaway probe extension before being trusted for the real one).
Add-Type -AssemblyName System.Net.WebSockets.Client -ErrorAction SilentlyContinue

$targetsNow = Invoke-RestMethod -Uri "http://127.0.0.1:$CdpPort/json" -TimeoutSec 5
$sw = $targetsNow | Where-Object { $_.type -eq "service_worker" -and $_.url -like "chrome-extension://*$ExtensionUrlFragment" }
if (-not $sw) {
    Write-Output "ERROR:NO_SERVICE_WORKER_FOUND"
    exit 1
}
$wsUrl = $sw[0].webSocketDebuggerUrl

$ws = New-Object System.Net.WebSockets.ClientWebSocket
$ws.ConnectAsync([System.Uri]$wsUrl, [System.Threading.CancellationToken]::None).Wait()

function Send-Cdp($id, $method, $paramsJson) {
    $msg = "{`"id`":$id,`"method`":`"$method`",`"params`":$paramsJson}"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($msg)
    $seg = New-Object System.ArraySegment[byte] (,$bytes)
    $ws.SendAsync($seg, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, [System.Threading.CancellationToken]::None).Wait()
}
function Receive-Cdp() {
    $buffer = New-Object byte[] 16384
    $seg = New-Object System.ArraySegment[byte] (,$buffer)
    $result = $ws.ReceiveAsync($seg, [System.Threading.CancellationToken]::None).Result
    return [System.Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count)
}
function Wait-ForId($targetId, $timeoutSec) {
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        $msg = Receive-Cdp
        if ($msg -match "`"id`":$targetId") { return $msg }
    }
    return $null
}

Send-Cdp 1 "Runtime.enable" "{}"
Wait-ForId 1 5 | Out-Null
$expr = "(async () => JSON.stringify(await Promise.all([chrome.action.getTitle({}), chrome.action.getBadgeText({})])))()"
Send-Cdp 2 "Runtime.evaluate" "{`"expression`":`"$expr`",`"awaitPromise`":true,`"returnByValue`":true}"
$resp = Wait-ForId 2 8
$ws.Dispose()
Write-Output "RESULT:$resp"
