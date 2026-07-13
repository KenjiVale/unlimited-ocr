[CmdletBinding()]
param([switch]$NoBrowser,[ValidateRange(1,65535)][int]$BackendPort=8000,[ValidateRange(1,65535)][int]$FrontendPort=3000)
$ErrorActionPreference='Stop'; $root=Split-Path $PSScriptRoot -Parent; . $PSScriptRoot\local-lifecycle.ps1
if (-not (Test-Path "$root\.env")) { throw '.env missing; run scripts\setup-windows.ps1' }
if ((Get-LocalListener $BackendPort) -or (Get-LocalListener $FrontendPort)) { throw 'Configured application port is already in use.' }
& $PSScriptRoot\preflight.ps1 -BackendPort $BackendPort -FrontendPort $FrontendPort
$runtime=Get-LocalRuntimePath $root; New-Item -ItemType Directory -Force $runtime|Out-Null
''|Set-Content "$runtime\backend.log"; ''|Set-Content "$runtime\backend.err.log"; ''|Set-Content "$runtime\frontend.log"; ''|Set-Content "$runtime\frontend.err.log"
$clock=[Diagnostics.Stopwatch]::StartNew(); $backend=$null; $frontend=$null
try {
  $backend=Start-Process -FilePath "$root\.venv\Scripts\python.exe" -ArgumentList '-m','uvicorn','app.main:app','--app-dir','services\api','--host','127.0.0.1','--port',$BackendPort -WorkingDirectory $root -RedirectStandardOutput "$runtime\backend.log" -RedirectStandardError "$runtime\backend.err.log" -PassThru
  $node=(Get-Command node -ErrorAction Stop).Source; $nextBin="$root\apps\web\node_modules\next\dist\bin\next"
  $frontend=Start-Process -FilePath $node -ArgumentList $nextBin,'start','--hostname','127.0.0.1','--port',$FrontendPort -WorkingDirectory "$root\apps\web" -RedirectStandardOutput "$runtime\frontend.log" -RedirectStandardError "$runtime\frontend.err.log" -PassThru
  for($i=0;$i -lt 60;$i++){try{if((Invoke-WebRequest "http://127.0.0.1:$BackendPort/api/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200){break}}catch{};Start-Sleep -Milliseconds 500}; if(-not(Get-LocalListener $BackendPort)){throw 'Backend readiness timeout'}; $backendMs=$clock.ElapsedMilliseconds
  for($i=0;$i -lt 60;$i++){try{if((Invoke-WebRequest "http://127.0.0.1:$FrontendPort" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200){break}}catch{};Start-Sleep -Milliseconds 500}; if(-not(Get-LocalListener $FrontendPort)){throw 'Frontend readiness timeout'}; $frontendMs=$clock.ElapsedMilliseconds
  Write-LocalListenerMetadata $root 'backend' $BackendPort ([int](Get-LocalListener $BackendPort).OwningProcess); Write-LocalListenerMetadata $root 'frontend' $FrontendPort ([int](Get-LocalListener $FrontendPort).OwningProcess)
  [pscustomobject]@{backend_ready_ms=$backendMs;frontend_ready_ms=$frontendMs;total_ms=$clock.ElapsedMilliseconds;backend_port=$BackendPort;frontend_port=$FrontendPort}|ConvertTo-Json|Set-Content "$runtime\startup.timings.json"
  Write-Host "Backend: http://127.0.0.1:$BackendPort"; Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
  if(-not $NoBrowser){Start-Process "http://127.0.0.1:$FrontendPort"}
} catch { try { Stop-LocalService $root 'frontend' $FrontendPort -Force } catch {}; try { Stop-LocalService $root 'backend' $BackendPort -Force } catch {}; throw }
