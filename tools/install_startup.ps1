# Starts ellora_display.py hidden at every Windows login.
#   powershell -ExecutionPolicy Bypass -File tools\install_startup.ps1 -- "C:\path\to\cat.gif" --12h
# Run again with new arguments to change them; delete the shortcut to stop:
#   shell:startup  ->  "Ellora65 Display.lnk"
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$AppArgs)

$pythonw = Join-Path (Split-Path (Get-Command python).Source) 'pythonw.exe'
$script  = Join-Path $PSScriptRoot 'ellora_display.py'
$quoted  = ($AppArgs | Where-Object { $_ -ne '--' } | ForEach-Object { '"' + $_ + '"' }) -join ' '

$link = Join-Path ([Environment]::GetFolderPath('Startup')) 'Ellora65 Display.lnk'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($link)
$shortcut.TargetPath       = $pythonw
$shortcut.Arguments        = "`"$script`" $quoted"
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Save()

Write-Host "Created $link"
Write-Host "  $pythonw $($shortcut.Arguments)"
