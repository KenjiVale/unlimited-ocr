$root=Split-Path $PSScriptRoot -Parent; . $PSScriptRoot\local-lifecycle.ps1
foreach($service in @(@{name='backend';port=8000},@{name='frontend';port=3000})){
  $listener=Get-LocalListener $service.port
  $tracked=Get-LocalTrackedPid $root $service.name
  if($listener){$p=Get-LocalProcessInfo ([int]$listener.OwningProcess);$owned=Test-LocalServiceOwnership $service.name $p $root;Write-Host "$($service.name) listener PID $($listener.OwningProcess), owned=$owned, tracked=$tracked"}
  elseif($tracked){Write-Host "$($service.name) stale PID metadata: $tracked"}
  else{Write-Host "$($service.name) stopped"}
}
try{$s=Invoke-RestMethod http://127.0.0.1:8000/api/system/worker -TimeoutSec 2;Write-Host "Worker $($s.state), queue $($s.queued_jobs), active $($s.active_job_id)";$m=Invoke-RestMethod http://127.0.0.1:8000/api/system/model -TimeoutSec 2;Write-Host "Model $($m.status), offline $($m.offline_mode)";$d=Invoke-RestMethod http://127.0.0.1:8000/api/system/storage -TimeoutSec 2;Write-Host "Free disk $($d.free_disk_bytes)"}catch{Write-Host 'Backend unavailable'}
