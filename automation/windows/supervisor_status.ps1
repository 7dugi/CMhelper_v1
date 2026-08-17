$Task = Get-ScheduledTask -TaskName "CMhelper_Supervisor" -ErrorAction SilentlyContinue
if ($Task) {
    Write-Host "Scheduled Task Status: $($Task.State)"
} else {
    Write-Host "Scheduled Task not found."
}

$Process = Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%automation.supervisor%'"
if ($Process) {
    if ($Process.Count -gt 1) {
        Write-Host "WARNING: Multiple Supervisor instances are running!"
        foreach ($p in $Process) {
            Write-Host "Supervisor is running (PID: $($p.ProcessId))"
        }
    } else {
        Write-Host "Supervisor is running (PID: $($Process.ProcessId))"
    }
} else {
    Write-Host "Supervisor is NOT running."
}
