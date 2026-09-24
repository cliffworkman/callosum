param(
    [Parameter(Mandatory=$true)][int]$EdgePid,
    [string]$ExtensionName = "Callosum Capture"
)
# PROVEN mechanism (empirically verified against a real Edge window before being trusted here):
# keyboard focus navigation (Tab) + Enter activation. Raw synthetic mouse clicks (SetCursorPos +
# mouse_event, and UI Automation InvokePattern/ExpandCollapsePattern/LegacyIAccessiblePattern) were
# all tried first and FAILED to activate Chromium's custom-drawn toolbar/flyout buttons -- clicking
# the unambiguous "New Tab" split-button DID work via raw mouse, proving synthetic input delivery
# itself was not broken, but the Extensions button and its flyout rows specifically never responded
# to any mouse-based mechanism in repeated tests. Tab-to-focus + Enter reliably reached and opened
# the Extensions flyout and its extension row every time it was tried. This is still real, OS-level
# keyboard input delivered to the real browser window (SendKeys -> the foreground window's input
# queue), not a synthetic message to the extension -- the same category of genuine external input as
# a mouse click, just a different input device.
#
# Separately verified against a throwaway probe extension (chrome.action.onClicked +
# chrome.scripting.executeScript reading document.title): after this exact click mechanism, the
# extension's title became "GESTURE_OK:<real page title>" and its badge became "OK", read back over
# CDP -- proof this click carries a real activeTab/user-gesture grant, not just an event firing.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class WinFocus {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
    public const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    public const uint MOUSEEVENTF_LEFTUP = 0x0004;
}
"@

function Find-EdgeWindow() {
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $all = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
    $matches = New-Object System.Collections.Generic.List[System.Windows.Automation.AutomationElement]
    foreach ($w in $all) {
        try {
            $p = Get-Process -Id $w.Current.ProcessId -ErrorAction SilentlyContinue
            if ($p -and $p.ProcessName -eq "msedge" -and $w.Current.Name) { $matches.Add($w) }
        } catch {}
    }
    return $matches
}

function Get-FocusName {
    try { return [System.Windows.Automation.AutomationElement]::FocusedElement.Current.Name } catch { return "" }
}

$windows = Find-EdgeWindow
if ($windows.Count -eq 0) {
    Write-Output "RESULT:NO_WINDOW"
    exit 1
}
# The real, largest top-level Edge window is the browser frame -- not a devtools/popup window that
# might also match the process-name filter.
$mainWindow = $windows | Sort-Object { $_.Current.BoundingRectangle.Width * $_.Current.BoundingRectangle.Height } -Descending | Select-Object -First 1
Write-Output "WINDOW_NAME:$($mainWindow.Current.Name)"

$h = $mainWindow.Current.NativeWindowHandle
[WinFocus]::SetForegroundWindow([IntPtr]$h) | Out-Null
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait("{ESC}")
Start-Sleep -Milliseconds 300

# F6 pane-cycling was observed to land unpredictably inside the omnibox's suggestion dropdown
# (once showing an unrelated clipboard-paste suggestion), which is not a safe, reproducible Tab-order
# anchor. Clicking "Refresh" was tried next, but on a real content-rich page (not the trivial local
# test pages used to first prove this mechanism) it RELOADS the page, which resets keyboard focus
# into the page's own DOM -- Tab then walks through the page's own many links/buttons and never
# reaches browser chrome within any reasonable budget. The address bar has no such side effect: it
# is unambiguously a chrome element, clicking it never navigates or reloads, and Tab forward from it
# stays within the toolbar (favorites star, Extensions, profile, ...) regardless of what page or how
# much content is loaded.
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$stack = New-Object System.Collections.Generic.Stack[System.Windows.Automation.AutomationElement]
$stack.Push($mainWindow)
$anchorBtn = $null
while ($stack.Count -gt 0) {
    $node = $stack.Pop()
    try { if ($node.Current.Name -eq "Address and search bar") { $anchorBtn = $node; break } } catch {}
    try {
        $c = $walker.GetFirstChild($node)
        while ($c -ne $null) { $stack.Push($c); $c = $walker.GetNextSibling($c) }
    } catch {}
}
if ($anchorBtn) {
    $r = $anchorBtn.Current.BoundingRectangle
    $cx = [int]($r.X + $r.Width/2); $cy = [int]($r.Y + $r.Height/2)
    [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($cx,$cy)
    Start-Sleep -Milliseconds 300
    [WinFocus]::mouse_event([WinFocus]::MOUSEEVENTF_LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 100
    [WinFocus]::mouse_event([WinFocus]::MOUSEEVENTF_LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
    Write-Output "ANCHORED_FOCUS_VIA_ADDRESS_BAR at $cx,$cy"
    Start-Sleep -Milliseconds 500
    # Clicking a non-empty address bar can surface a suggestions/history dropdown -- dismiss it so
    # the very next Tab moves within the toolbar, not into that dropdown's own items.
    [System.Windows.Forms.SendKeys]::SendWait("{ESC}")
    Start-Sleep -Milliseconds 300
} else {
    Write-Output "WARNING: Address bar not found for focus anchoring; proceeding with F6 fallback"
    [System.Windows.Forms.SendKeys]::SendWait("{F6}")
    Start-Sleep -Milliseconds 300
    [System.Windows.Forms.SendKeys]::SendWait("{F6}")
    Start-Sleep -Milliseconds 300
}

$foundDirect = $false
$openedFlyout = $false
for ($i = 0; $i -lt 25; $i++) {
    [System.Windows.Forms.SendKeys]::SendWait("{TAB}")
    Start-Sleep -Milliseconds 250
    $name = Get-FocusName
    Write-Output "TAB $i -> '$name'"
    if ($name -like "*$ExtensionName*") {
        Write-Output "FOUND_DIRECT:$name"
        $foundDirect = $true
        break
    }
    if ($name -eq "Extensions") {
        [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
        Start-Sleep -Milliseconds 800
        Write-Output "OPENED_EXT_MENU"
        $openedFlyout = $true
        break
    }
}

if ($foundDirect) {
    [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    Write-Output "RESULT:CLICKED_DIRECT via keyboard"
    exit 0
}

if (-not $openedFlyout) {
    Write-Output "RESULT:NEITHER_DIRECT_NOR_MENU_FOUND"
    exit 2
}

for ($i = 0; $i -lt 6; $i++) {
    [System.Windows.Forms.SendKeys]::SendWait("{TAB}")
    Start-Sleep -Milliseconds 250
    $name = Get-FocusName
    Write-Output "MENU_TAB $i -> '$name'"
    if ($name -like "*$ExtensionName*") {
        [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
        Write-Output "RESULT:CLICKED_VIA_MENU via keyboard"
        exit 0
    }
}
Write-Output "RESULT:NO_MENU_ITEM"
exit 3
