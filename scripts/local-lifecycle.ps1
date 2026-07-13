Set-StrictMode -Version Latest

function Get-LocalRuntimePath([string]$Root) { Join-Path $Root '.runtime' }
function Get-LocalPidPath([string]$Root, [string]$Name) { Join-Path (Get-LocalRuntimePath $Root) "$Name.pid" }
function Get-LocalMetadataPath([string]$Root, [string]$Name) { Join-Path (Get-LocalRuntimePath $Root) "$Name.process.json" }

function Get-LocalListener {
  param([int]$Port)
  $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
  if ($listeners.Count -gt 1) { throw "Ambiguous listeners on port $Port." }
  if ($listeners.Count -eq 1) { return $listeners[0] }
  return $null
}

function Get-LocalProcessInfo {
  param([int]$ProcessId)
  return Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
}

function Test-LocalServiceOwnership {
  param([string]$Name, $Process, [string]$Root)
  if (-not $Process) { return $false }
  $command = [string]$Process.CommandLine
  if ($Name -eq 'backend') {
    return $Process.Name -match '^python(\.exe)?$' -and $command -match 'uvicorn' -and $command -match 'services[\\/]api'
  }
  if ($Name -eq 'frontend') {
    return $Process.Name -match '^node(\.exe)?$' -and $command -match 'next' -and $command -match 'apps[\\/]web'
  }
  return $false
}

function Write-LocalListenerMetadata {
  param([string]$Root, [string]$Name, [int]$Port, [int]$ProcessId)
  $process = Get-LocalProcessInfo $ProcessId
  if (-not (Test-LocalServiceOwnership $Name $process $Root)) { throw "LISTENER_OWNERSHIP_UNVERIFIED: $Name PID $ProcessId" }
  $runtime = Get-LocalRuntimePath $Root
  New-Item -ItemType Directory -Force $runtime | Out-Null
  [pscustomobject]@{
    pid = $ProcessId; parent_pid = [int]$process.ParentProcessId; process_name = $process.Name
    command_line = [string]$process.CommandLine; port = $Port
    started_at = (Get-Date).ToUniversalTime().ToString('o'); repository_root = $Root
  } | ConvertTo-Json | Set-Content -LiteralPath (Get-LocalMetadataPath $Root $Name)
  $ProcessId | Set-Content -LiteralPath (Get-LocalPidPath $Root $Name)
}

function Remove-LocalRuntimeFiles {
  param([string]$Root, [string]$Name)
  Remove-Item -LiteralPath (Get-LocalPidPath $Root $Name),(Get-LocalMetadataPath $Root $Name) -Force -ErrorAction SilentlyContinue
}

function Get-LocalTrackedPid {
  param([string]$Root, [string]$Name)
  $metadataPath = Get-LocalMetadataPath $Root $Name
  if (Test-Path $metadataPath) {
    try { $metadata = Get-Content -Raw $metadataPath | ConvertFrom-Json; return [int]$metadata.pid } catch { throw "Invalid $Name metadata file." }
  }
  $pidPath = Get-LocalPidPath $Root $Name
  if (Test-Path $pidPath) {
    try { return [int](Get-Content -Raw $pidPath) } catch { throw "Invalid $Name PID file." }
  }
  return $null
}

function Stop-LocalService {
  param([string]$Root, [string]$Name, [int]$Port, [switch]$Force)
  $listener = Get-LocalListener $Port
  $trackedPid = Get-LocalTrackedPid $Root $Name
  if ($listener) {
    $listenerProcessId = [int]$listener.OwningProcess
    $process = Get-LocalProcessInfo $listenerProcessId
    if (-not (Test-LocalServiceOwnership $Name $process $Root)) { throw "PORT_OCCUPIED_BY_UNRELATED_PROCESS: port $Port PID $listenerProcessId" }
    if (-not $trackedPid) { Write-Host "APPLICATION_LISTENER_RECOVERED: $Name PID $listenerProcessId"; Write-LocalListenerMetadata $Root $Name $Port $listenerProcessId }
    elseif ($trackedPid -ne $listenerProcessId) { Write-Host "STALE_PID_FILE_REMOVED: $Name PID $trackedPid replaced by listener $listenerProcessId"; Write-LocalListenerMetadata $Root $Name $Port $listenerProcessId }
    Stop-Process -Id $listenerProcessId -Force:$Force -ErrorAction Stop
  } elseif ($trackedPid) {
    $process = Get-LocalProcessInfo $trackedPid
    if ($process -and (Test-LocalServiceOwnership $Name $process $Root)) { Stop-Process -Id $trackedPid -Force:$Force -ErrorAction Stop }
    else { Write-Host "STALE_PID_FILE_REMOVED: $Name PID $trackedPid" }
  } else { Write-Host "$Name already stopped"; return }
  for ($i=0; $i -lt 60; $i++) { if (-not (Get-LocalListener $Port)) { Remove-LocalRuntimeFiles $Root $Name; Write-Host "Stopped $Name listener"; return }; Start-Sleep -Milliseconds 500 }
  throw "$Name listener did not release port $Port"
}

function Test-LocalCleanup {
  param([string]$Root, [int]$BackendPort=8000, [int]$FrontendPort=3000)
  $backend = Get-LocalListener $BackendPort; $frontend = Get-LocalListener $FrontendPort
  $files = @((Get-LocalPidPath $Root 'backend'),(Get-LocalPidPath $Root 'frontend'),(Get-LocalMetadataPath $Root 'backend'),(Get-LocalMetadataPath $Root 'frontend'))
  $remaining = @($files | Where-Object { Test-Path $_ })
  [pscustomobject]@{ backend_port_free = -not [bool]$backend; frontend_port_free = -not [bool]$frontend; pid_metadata_files_absent = $remaining.Count -eq 0; remaining_runtime_files = $remaining; valid = (-not $backend -and -not $frontend -and $remaining.Count -eq 0) }
}
