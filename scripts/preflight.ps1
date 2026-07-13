[CmdletBinding()]
param([int]$BackendPort=8000,[int]$FrontendPort=3000)
$ErrorActionPreference='Stop'; $root=Split-Path $PSScriptRoot -Parent; Set-Location $root; $failed=$false
function Check($name,$script){try{& $script; Write-Host "PASS  $name" -ForegroundColor Green}catch{Write-Host "FAIL  $name - $($_.Exception.Message)" -ForegroundColor Red;$script:failed=$true}}
Check 'Python 3.12' { if(-not (Test-Path '.venv\Scripts\python.exe')){throw 'Run setup-windows.ps1'}; $v=& .venv\Scripts\python.exe --version; if($v -notmatch '3\.12'){throw $v} }
Check 'Node.js' { if(-not (Get-Command node -ErrorAction SilentlyContinue)){throw 'Node.js LTS missing'} }
Check 'pnpm' { if(-not (Get-Command pnpm -ErrorAction SilentlyContinue)){throw 'Enable Corepack or install pnpm'} }
Check 'Model files' { if(-not (Test-Path 'data\models\Unlimited-OCR\config.json')){throw 'Run download_model.py explicitly'} }
Check 'Offline model files' { if((Select-String -Path .env -Pattern '^HF_HUB_OFFLINE=1' -Quiet) -and -not (Get-ChildItem 'data\models\Unlimited-OCR' -Filter '*.safetensors' -File)){throw 'Offline model weights missing'} }
Check 'CUDA' { & .venv\Scripts\python.exe scripts\check_cuda.py | Out-Null; if($LASTEXITCODE -ne 0){throw 'CUDA check failed'} }
Check 'Backend dependencies' { if(-not (Test-Path 'services\api\app\main.py')){throw 'Backend source missing'}; & .venv\Scripts\python.exe -c "import fastapi, sqlalchemy, fitz, torch" }
Check 'Frontend dependencies' { if(-not (Test-Path 'apps\web\node_modules\next\package.json')){throw 'Run pnpm install'} }
Check 'Production frontend build' { if(-not (Test-Path 'apps\web\.next\BUILD_ID')){throw 'Run Set-Location apps\web; pnpm exec next build'} }
Check 'Database location' { if(-not (Test-Path 'data\app.db')){throw 'Database has not been initialized'} }
Check 'Data write access' { New-Item -ItemType Directory -Force data,.runtime | Out-Null; $p='data\.write-test'; Set-Content $p 'ok'; Remove-Item $p }
Check 'Minimum free disk' { $required=[int64](5 * 1GB); $driveLetter=(Get-Location).Path.Substring(0,1); $free=[int64]([System.IO.DriveInfo]::new("${driveLetter}:\")).AvailableFreeSpace; if($free -lt $required){throw "Free disk below 5 GB: $free"} }
foreach($p in @($BackendPort,$FrontendPort)){if(Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue){Write-Host "FAIL  Port $p is already listening" -ForegroundColor Red;$failed=$true}else{Write-Host "PASS  Port $p available" -ForegroundColor Green}}
if($failed){exit 1}
