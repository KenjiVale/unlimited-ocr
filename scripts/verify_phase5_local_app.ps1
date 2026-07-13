[CmdletBinding()]
param([switch]$KeepRunning)
$ErrorActionPreference='Stop'; $root=Split-Path $PSScriptRoot -Parent; Set-Location $root; . $PSScriptRoot\local-lifecycle.ps1
$audit=[ordered]@{wrapper_pid=$PID;started_at=(Get-Date).ToUniversalTime().ToString('o');before=@{};after=@{};functional_checks=$false;cleanup=$null;error=$null}
function Get-PortAudit([int]$Port){$l=Get-LocalListener $Port;if(-not $l){return $null};$p=Get-LocalProcessInfo ([int]$l.OwningProcess);return @{pid=[int]$l.OwningProcess;parent_pid=[int]$p.ParentProcessId;name=$p.Name;command_line=$p.CommandLine;executable_path=$p.ExecutablePath}}
$audit.before.backend_listener=Get-PortAudit 8000;$audit.before.frontend_listener=Get-PortAudit 3000
$started=$false
try {
  & $PSScriptRoot\preflight.ps1
  & $PSScriptRoot\start-local.ps1 -NoBrowser; $started=$true
  $audit.backend_listener=Get-PortAudit 8000;$audit.frontend_listener=Get-PortAudit 3000
  $audit.pid_files=@{backend=(Get-Content '.runtime\backend.pid' -ErrorAction SilentlyContinue);frontend=(Get-Content '.runtime\frontend.pid' -ErrorAction SilentlyContinue)}
  $image=Join-Path $root 'data\models\Unlimited-OCR\assets\Unlimited-OCR.png'
  $imageEvidence=& .\.venv\Scripts\python.exe scripts\verify_phase2_api.py $image | Out-String | ConvertFrom-Json
  $pdfEvidence=& .\.venv\Scripts\python.exe scripts\verify_phase3_pdf.py | Out-String | ConvertFrom-Json
  foreach($kind in 'markdown','text','json'){$target=Join-Path $root ".runtime\phase5-$kind.download";Invoke-WebRequest "http://127.0.0.1:8000/api/ocr/jobs/$($pdfEvidence.job_id)/download/$kind" -OutFile $target -UseBasicParsing;if(-not(Test-Path $target) -or (Get-Item $target).Length -eq 0){throw "Download failed: $kind"}}
  Invoke-WebRequest 'http://127.0.0.1:3000/jobs' -UseBasicParsing|Out-Null;Invoke-WebRequest "http://127.0.0.1:8000/api/ocr/jobs/$($pdfEvidence.job_id)/integrity" -UseBasicParsing|Out-Null
  $audit.functional_checks=$true;[pscustomobject]@{image_job=$imageEvidence.first.job_id;pdf_job=$pdfEvidence.job_id;downloads_verified=$true;frontend_available=$true}|ConvertTo-Json -Compress
} catch {$audit.error=$_.Exception.Message;throw} finally {
  if($started -and -not $KeepRunning){try{& $PSScriptRoot\stop-local.ps1}catch{$audit.cleanup_error=$_.Exception.Message}}
  $audit.after.backend_listener=Get-PortAudit 8000;$audit.after.frontend_listener=Get-PortAudit 3000;$audit.cleanup=Test-LocalCleanup $root
  $audit.completed_at=(Get-Date).ToUniversalTime().ToString('o');$audit|ConvertTo-Json -Depth 6|Set-Content '.runtime\phase6-process-audit.json'
  if(-not $KeepRunning -and -not $audit.cleanup.valid){throw 'Verifier cleanup failed; see .runtime/phase6-process-audit.json'}
}
