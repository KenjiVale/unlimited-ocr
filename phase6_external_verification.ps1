param(
    [string]$RepositoryRoot = "D:\Projects\unlimited-ocr"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $RepositoryRoot

$repoRoot = (Get-Location).Path
$runtimeDir = Join-Path $repoRoot ".runtime"

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

function Get-PortListenerEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $listeners = @(
        Get-NetTCPConnection `
            -State Listen `
            -LocalPort $Port `
            -ErrorAction SilentlyContinue
    )

    $results = @()

    foreach ($listener in $listeners) {
        $process = Get-CimInstance `
            -ClassName Win32_Process `
            -Filter "ProcessId=$($listener.OwningProcess)" `
            -ErrorAction SilentlyContinue

        $results += [ordered]@{
            port = $Port
            owning_pid = $listener.OwningProcess
            process_name = $process.Name
            parent_process_id = $process.ParentProcessId
            executable_path = $process.ExecutablePath
            command_line = $process.CommandLine
        }
    }

    return $results
}

function Get-RemainingProjectProcesses {
    $escapedRoot = [regex]::Escape($repoRoot)

    $processes = @(
        Get-CimInstance -ClassName Win32_Process |
            Where-Object {
                $_.CommandLine -and
                $_.CommandLine -match $escapedRoot -and
                (
                    $_.CommandLine -match "uvicorn" -or
                    $_.CommandLine -match "next(\.cmd)?\s+start" -or
                    $_.CommandLine -match "next-server" -or
                    $_.CommandLine -match "start-local\.ps1"
                )
            }
    )

    $results = @()

    foreach ($process in $processes) {
        $results += [ordered]@{
            pid = $process.ProcessId
            parent_process_id = $process.ParentProcessId
            process_name = $process.Name
            executable_path = $process.ExecutablePath
            command_line = $process.CommandLine
        }
    }

    return $results
}

function Write-VerifierEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [int]$RunNumber,

        [Parameter(Mandatory = $true)]
        [int]$ExitCode,

        [Parameter(Mandatory = $true)]
        [double]$DurationMilliseconds
    )

    $backendListeners = @(Get-PortListenerEvidence -Port 8000)
    $frontendListeners = @(Get-PortListenerEvidence -Port 3000)
    $remainingProcesses = @(Get-RemainingProjectProcesses)

    $backendPidPath = Join-Path $runtimeDir "backend.pid"
    $frontendPidPath = Join-Path $runtimeDir "frontend.pid"
    $backendMetadataPath = Join-Path $runtimeDir "backend.process.json"
    $frontendMetadataPath = Join-Path $runtimeDir "frontend.process.json"

    $cleanupPassed = (
        $ExitCode -eq 0 -and
        $backendListeners.Count -eq 0 -and
        $frontendListeners.Count -eq 0 -and
        -not (Test-Path $backendPidPath) -and
        -not (Test-Path $frontendPidPath) -and
        -not (Test-Path $backendMetadataPath) -and
        -not (Test-Path $frontendMetadataPath) -and
        $remainingProcesses.Count -eq 0
    )

    $evidence = [ordered]@{
        run_number = $RunNumber
        recorded_at = (Get-Date).ToString("o")
        execution_environment = "Normal non-administrator PowerShell"
        repository_root = $repoRoot
        exit_code = $ExitCode
        duration_ms = [math]::Round($DurationMilliseconds)
        backend_port_free = ($backendListeners.Count -eq 0)
        frontend_port_free = ($frontendListeners.Count -eq 0)
        backend_listeners = $backendListeners
        frontend_listeners = $frontendListeners
        backend_pid_file_exists = Test-Path $backendPidPath
        frontend_pid_file_exists = Test-Path $frontendPidPath
        backend_metadata_exists = Test-Path $backendMetadataPath
        frontend_metadata_exists = Test-Path $frontendMetadataPath
        remaining_project_processes = $remainingProcesses
        cleanup_passed = $cleanupPassed
    }

    $outputPath = Join-Path $runtimeDir "phase6-verifier-run$RunNumber.json"

    $evidence |
        ConvertTo-Json -Depth 10 |
        Set-Content -Path $outputPath -Encoding UTF8

    return $evidence
}

function Assert-CleanState {
    $backendListeners = @(Get-PortListenerEvidence -Port 8000)
    $frontendListeners = @(Get-PortListenerEvidence -Port 3000)
    $remainingProcesses = @(Get-RemainingProjectProcesses)

    if ($backendListeners.Count -gt 0) {
        throw "Port 8000 is still occupied."
    }

    if ($frontendListeners.Count -gt 0) {
        throw "Port 3000 is still occupied."
    }

    if ($remainingProcesses.Count -gt 0) {
        throw "Verified repository application processes are still running."
    }
}

$oldAudit = Join-Path $runtimeDir "phase6-process-audit.json"

if (Test-Path $oldAudit) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupAudit = Join-Path $runtimeDir "phase6-process-audit-before-external-$timestamp.json"
    Copy-Item $oldAudit $backupAudit
}

Write-Host "========== INITIAL STATE =========="

& .\scripts\status-local.ps1
& .\scripts\stop-local.ps1

Assert-CleanState

Write-Host ""
Write-Host "========== VERIFIER RUN 1 =========="

$run1Started = Get-Date
& .\scripts\verify_phase5_local_app.ps1
$run1ExitCode = $LASTEXITCODE
$run1Duration = (Get-Date) - $run1Started

$run1Arguments = @{
    RunNumber = 1
    ExitCode = $run1ExitCode
    DurationMilliseconds = $run1Duration.TotalMilliseconds
}

$run1Evidence = Write-VerifierEvidence @run1Arguments

if (Test-Path $oldAudit) {
    Copy-Item $oldAudit (Join-Path $runtimeDir "phase6-process-audit-run1.json") -Force
}

Write-Host "Run 1 exit code: $run1ExitCode"
Write-Host "Run 1 cleanup passed: $($run1Evidence.cleanup_passed)"

if (-not $run1Evidence.cleanup_passed) {
    Write-Host ""
    Write-Host "Run 1 failed. Run 2 will not be started."
    Write-Host "Preserve terminal output and .runtime evidence files."
    exit 1
}

Write-Host ""
Write-Host "========== VERIFIER RUN 2 =========="

$run2Started = Get-Date
& .\scripts\verify_phase5_local_app.ps1
$run2ExitCode = $LASTEXITCODE
$run2Duration = (Get-Date) - $run2Started

$run2Arguments = @{
    RunNumber = 2
    ExitCode = $run2ExitCode
    DurationMilliseconds = $run2Duration.TotalMilliseconds
}

$run2Evidence = Write-VerifierEvidence @run2Arguments

if (Test-Path $oldAudit) {
    Copy-Item $oldAudit (Join-Path $runtimeDir "phase6-process-audit-run2.json") -Force
}

Write-Host "Run 2 exit code: $run2ExitCode"
Write-Host "Run 2 cleanup passed: $($run2Evidence.cleanup_passed)"

Write-Host ""
Write-Host "========== FINAL RESULT =========="
Write-Host "Run 1 exit code: $run1ExitCode"
Write-Host "Run 1 cleanup passed: $($run1Evidence.cleanup_passed)"
Write-Host "Run 2 exit code: $run2ExitCode"
Write-Host "Run 2 cleanup passed: $($run2Evidence.cleanup_passed)"
Write-Host "Backend port free: $($run2Evidence.backend_port_free)"
Write-Host "Frontend port free: $($run2Evidence.frontend_port_free)"
Write-Host "Backend PID exists: $($run2Evidence.backend_pid_file_exists)"
Write-Host "Frontend PID exists: $($run2Evidence.frontend_pid_file_exists)"
Write-Host "Backend metadata exists: $($run2Evidence.backend_metadata_exists)"
Write-Host "Frontend metadata exists: $($run2Evidence.frontend_metadata_exists)"
Write-Host "Remaining project processes: $($run2Evidence.remaining_project_processes.Count)"

& .\scripts\status-local.ps1

if (-not $run2Evidence.cleanup_passed) {
    exit 1
}

exit 0
