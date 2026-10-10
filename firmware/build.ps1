# Builds the Ellora65 "display" keymap with QMK MSYS and copies the .hex here.
#   powershell -ExecutionPolicy Bypass -File firmware\build.ps1
$ErrorActionPreference = 'Stop'

$qmkHome   = Join-Path $env:USERPROFILE 'qmk_firmware'
$keymapSrc = Join-Path $PSScriptRoot 'keymaps\display'
$keymapDst = Join-Path $qmkHome 'keyboards\kikoslab\ellora65\keymaps\display'

New-Item -ItemType Directory -Force $keymapDst | Out-Null
Copy-Item -Force (Join-Path $keymapSrc '*') $keymapDst

$env:MSYSTEM = 'MINGW64'
$env:CHERE_INVOKING = '1'
$qmkPosix = '/' + ($qmkHome -replace ':', '' -replace '\\', '/')
& C:\QMK_MSYS\usr\bin\bash.exe -lc "cd '$qmkPosix' && qmk config user.hide_welcome=True >/dev/null && qmk compile -kb kikoslab/ellora65 -km display"
if ($LASTEXITCODE -ne 0) { throw "qmk compile failed" }

Copy-Item -Force (Join-Path $qmkHome 'kikoslab_ellora65_display.hex') (Split-Path $PSScriptRoot)
Write-Host "Firmware: $(Join-Path (Split-Path $PSScriptRoot) 'kikoslab_ellora65_display.hex')"
