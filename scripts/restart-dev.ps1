param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

Write-Host "Parando servidor..."
& "$PSScriptRoot\stop-dev.ps1" -Port $Port

Start-Sleep -Seconds 1

Write-Host "Iniciando servidor..."
& "$PSScriptRoot\start-dev.ps1" -Port $Port
