param(
    [Parameter(Mandatory=$true)][int]$CdpPort,
    [int]$TimeoutSec = 25
)
Add-Type -AssemblyName System.Net.WebSockets.Client -ErrorAction SilentlyContinue
$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
    try {
        $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$CdpPort/json" -TimeoutSec 3
        $page = $targets | Where-Object { $_.type -eq "page" } | Select-Object -First 1
        if ($page) {
            $ws = New-Object System.Net.WebSockets.ClientWebSocket
            $ws.ConnectAsync([System.Uri]$page.webSocketDebuggerUrl, [System.Threading.CancellationToken]::None).Wait()
            $msg = '{"id":1,"method":"Runtime.evaluate","params":{"expression":"document.readyState","returnByValue":true}}'
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($msg)
            $seg = New-Object System.ArraySegment[byte] (,$bytes)
            $ws.SendAsync($seg, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, [System.Threading.CancellationToken]::None).Wait()
            $buffer = New-Object byte[] 8192
            $rseg = New-Object System.ArraySegment[byte] (,$buffer)
            $result = $ws.ReceiveAsync($rseg, [System.Threading.CancellationToken]::None).Result
            $resp = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count)
            $ws.Dispose()
            if ($resp -match '"value":"complete"') {
                Write-Output "READY"
                exit 0
            }
        }
    } catch {}
    Start-Sleep -Milliseconds 500
}
Write-Output "TIMEOUT"
exit 1
