$RepoRoot = Split-Path (Split-Path $PSScriptRoot)
$PythonPath = (Get-Command python).Source
if (-not $PythonPath) {
    Write-Host "Python not found in PATH."
    exit 1
}

$WrapperPath = Join-Path $PSScriptRoot "supervisor_runner.bat"
$WrapperContent = @"
@echo off
cd /d "$RepoRoot"
"$PythonPath" -m automation.supervisor
"@
Set-Content -Path $WrapperPath -Value $WrapperContent

# Register task using schtasks to avoid PS admin requirements for AtLogon
# It may still prompt or fail, but /sc daily usually works for standard users. We will try onlogon.
$SchtasksResult = Start-Process -FilePath "schtasks" -ArgumentList "/create /tn `"CMhelper_Supervisor`" /tr `"$WrapperPath`" /sc onlogon /f" -Wait -NoNewWindow -PassThru
if ($SchtasksResult.ExitCode -ne 0) {
    Write-Host "Failed to create OnLogon task. Falling back to daily..."
    Start-Process -FilePath "schtasks" -ArgumentList "/create /tn `"CMhelper_Supervisor`" /tr `"$WrapperPath`" /sc daily /st 00:00 /f" -Wait -NoNewWindow
}

Write-Host "Supervisor task installed successfully."
Write-Host "RepoRoot: $RepoRoot"
Write-Host "Python: $PythonPath"
