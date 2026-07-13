param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$tmpDir = Join-Path $root '.tmp'
if (-not (Test-Path $tmpDir)) {
    New-Item -ItemType Directory -Path $tmpDir | Out-Null
}

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw "Python virtualenv not found at $python"
}

$ngrok = (Get-Command ngrok -ErrorAction Stop).Source

$uvicornOut = Join-Path $tmpDir "uvicorn$Port.out.log"
$uvicornErr = Join-Path $tmpDir "uvicorn$Port.err.log"
$ngrokOut = Join-Path $tmpDir 'ngrok.out.log'
$ngrokErr = Join-Path $tmpDir 'ngrok.err.log'

Start-Process -WindowStyle Hidden `
    -FilePath $python `
    -WorkingDirectory $root `
    -ArgumentList @('-m', 'uvicorn', 'frontend.app:app', '--host', '127.0.0.1', '--port', $Port) `
    -RedirectStandardOutput $uvicornOut `
    -RedirectStandardError $uvicornErr | Out-Null

$schedulerRunning = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match 'python' -and $_.CommandLine -match 'etl[\\/]scheduler\.py'
}
if (-not $schedulerRunning) {
    $schedulerOut = Join-Path $tmpDir 'scheduler.out.log'
    $schedulerErr = Join-Path $tmpDir 'scheduler.err.log'
    Start-Process -WindowStyle Hidden `
        -FilePath $python `
        -WorkingDirectory $root `
        -ArgumentList @('etl\scheduler.py') `
        -RedirectStandardOutput $schedulerOut `
        -RedirectStandardError $schedulerErr | Out-Null
    Write-Host "Scheduler ETL iniciado (log: etl\scheduler.log)"
} else {
    Write-Host "Scheduler ETL ja em execucao (PID $($schedulerRunning[0].ProcessId))"
}

Start-Sleep -Seconds 2

Start-Process -WindowStyle Hidden `
    -FilePath $ngrok `
    -ArgumentList @('http', "127.0.0.1:$Port", '--log=stdout', '--log-format=logfmt') `
    -RedirectStandardOutput $ngrokOut `
    -RedirectStandardError $ngrokErr | Out-Null

$deadline = (Get-Date).AddSeconds(20)
$publicUrl = $null
while ((Get-Date) -lt $deadline -and -not $publicUrl) {
    Start-Sleep -Seconds 1
    try {
        $json = Invoke-WebRequest 'http://127.0.0.1:4040/api/tunnels' -UseBasicParsing
        $data = $json.Content | ConvertFrom-Json
        $publicUrl = $data.tunnels | Select-Object -First 1 -ExpandProperty public_url
    } catch {
        $publicUrl = $null
    }
}

Write-Host "Servidor local: http://127.0.0.1:$Port"
if ($publicUrl) {
    Write-Host "Ngrok: $publicUrl"
} else {
    Write-Host "Ngrok iniciado, mas a URL publica ainda nao apareceu. Verifique $ngrokErr e $ngrokOut"
}
