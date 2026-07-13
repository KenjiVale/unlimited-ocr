[CmdletBinding()]
param([switch]$Force)
$ErrorActionPreference='Stop'; $root=Split-Path $PSScriptRoot -Parent; . $PSScriptRoot\local-lifecycle.ps1
Stop-LocalService $root 'frontend' 3000 -Force:$Force
Stop-LocalService $root 'backend' 8000 -Force:$Force
$cleanup=Test-LocalCleanup $root
if(-not $cleanup.valid){$cleanup|ConvertTo-Json;throw 'Local cleanup verification failed'}
$cleanup|ConvertTo-Json
