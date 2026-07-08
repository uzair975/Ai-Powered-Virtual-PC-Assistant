param(
    [string]$Hotkey = "CTRL+ALT+J",
    [string]$Mode = "real",
    [string]$ShortcutName = "Jarvis Agent"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runnerScript = Join-Path $projectRoot "run_integrated.py"

if (-not (Test-Path $runnerScript)) {
    throw "run_integrated.py not found at $runnerScript"
}

$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
$python = (Get-Command python -ErrorAction SilentlyContinue).Source

if ($pythonw) {
    $pythonExe = $pythonw
} elseif ($python) {
    $pythonExe = $python
} else {
    throw "Python was not found on PATH."
}

$programsDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$shortcutPath = Join-Path $programsDir "$ShortcutName.lnk"

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonExe
$shortcut.Arguments = "`"$runnerScript`" --mode $Mode"
$shortcut.WorkingDirectory = $projectRoot
$shortcut.WindowStyle = 1
$shortcut.Description = "Launch Jarvis frontend + backend"
$shortcut.IconLocation = "$pythonExe,0"
$shortcut.Hotkey = $Hotkey
$shortcut.Save()

Write-Host "Installed shortcut: $shortcutPath"
Write-Host "Hotkey: $Hotkey"
Write-Host "Target: $pythonExe"
Write-Host "Args: `"$runnerScript`" --mode $Mode"
