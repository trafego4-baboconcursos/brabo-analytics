# Mantem o checkout local sempre na ultima versao publicada no git e o
# servidor rodando com ela -- util quando outro dev (ou o Claude) esta
# commitando direto na main e voce quer sempre ver o que ha de mais novo
# sem lembrar de rodar "git pull" e reiniciar o servidor manualmente.
#
# O que faz, em loop:
#   1. git fetch da origin
#   2. Se origin/main tiver commits novos E o working tree estiver limpo
#      (sem mudanca local sua sem commit), da git pull
#   3. Reinicia o servidor uvicorn pra garantir que o codigo Python novo
#      seja carregado (templates recarregam sozinhos com --reload, mas
#      mudanca em .py as vezes nao pega sem reiniciar o processo)
#
# Se voce tiver mudancas locais sem commit, o script AVISA e pula o pull
# daquela rodada (nunca descarta trabalho seu sem avisar).
#
# Uso:
#   powershell -File scripts\watch-and-run.ps1                    # porta 8000, checa a cada 60s
#   powershell -File scripts\watch-and-run.ps1 -Port 8001 -IntervalSeconds 30

param(
    [int]$Port = 8000,
    [int]$IntervalSeconds = 60
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$serverProcess = $null

function Start-Server {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Iniciando servidor em http://127.0.0.1:$Port ..."
    $script:serverProcess = Start-Process -FilePath "python" `
        -ArgumentList "-m", "uvicorn", "frontend.app:app", "--reload", "--port", $Port `
        -WindowStyle Hidden -PassThru
}

function Stop-Server {
    if ($script:serverProcess -and -not $script:serverProcess.HasExited) {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Parando servidor..."
        Stop-Process -Id $script:serverProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

try {
    Start-Server
    Write-Host "Observando origin/main a cada $IntervalSeconds s. Ctrl+C para sair."

    while ($true) {
        Start-Sleep -Seconds $IntervalSeconds

        git fetch origin main 2>&1 | Out-Null
        $localRev = git rev-parse main
        $remoteRev = git rev-parse origin/main

        if ($localRev -ne $remoteRev) {
            $dirty = git status --porcelain
            if ($dirty) {
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Ha versao nova (origin/main mudou) mas voce tem mudancas locais sem commit -- pulando o pull automatico pra nao misturar. Faca commit/stash e o script atualiza na proxima rodada."
                continue
            }

            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Nova versao encontrada, atualizando..."
            git pull origin main
            Stop-Server
            Start-Sleep -Seconds 1
            Start-Server
            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Atualizado e servidor reiniciado."
        }
    }
}
finally {
    Stop-Server
}
