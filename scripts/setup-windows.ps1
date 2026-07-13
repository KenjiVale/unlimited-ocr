[CmdletBinding()]
param([switch]$DownloadModel,[switch]$RunTests)
$ErrorActionPreference='Stop'; $root=Split-Path $PSScriptRoot -Parent; Set-Location $root
if(-not (Get-Command py -ErrorAction SilentlyContinue)){throw 'Install Python 3.12 first'}
if(-not (Test-Path '.venv\Scripts\python.exe')){py -3.12 -m venv .venv}
& .venv\Scripts\python.exe -m pip install -e '.\services\api[test,ocr]'
if(-not (Test-Path '.env')){Copy-Item .env.example .env}
New-Item -ItemType Directory -Force data\uploads,data\pages,data\outputs,data\models,.runtime | Out-Null
if($DownloadModel){& .venv\Scripts\python.exe scripts\download_model.py; if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}}
& .venv\Scripts\python.exe -c "from app.db import Database; Database('sqlite:///./data/app.db').initialize()" -- 2>$null
if(-not (Get-Command pnpm -ErrorAction SilentlyContinue)){throw 'Install pnpm with Corepack, then rerun'}
pnpm install
Push-Location apps\web
pnpm exec next build
Pop-Location
if($RunTests){Push-Location services\api; & ..\..\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider; Pop-Location}
Write-Host 'Setup complete. Next: .\scripts\start-local.ps1'
