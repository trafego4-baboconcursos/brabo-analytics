param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

function Stop-ByMatch {
    param(
        [string]$Name,
        [string]$Pattern
    )

    $procs = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match $Name -and $_.CommandLine -match $Pattern
    }

    foreach ($proc in $procs) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Write-Host "Stopped $($proc.Name) (PID $($proc.ProcessId))"
        } catch {
            Write-Host "Could not stop $($proc.Name) (PID $($proc.ProcessId)): $($_.Exception.Message)"
        }
    }
}

Stop-ByMatch -Name 'python.exe|pythonw.exe' -Pattern "uvicorn frontend\.app:app.*--port $Port"
Stop-ByMatch -Name 'ngrok.exe' -Pattern "http 127\.0\.0\.1:$Port"

try {
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
    foreach ($listener in $listeners) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
} catch {
    Write-Host "No listener cleanup needed on port $Port."
}
