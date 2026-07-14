# Gera um backup de tudo que NAO esta no GitHub (segredos, dados, memoria do Claude).
# O codigo em si e recuperado com: git clone https://github.com/trafego4-baboconcursos/brabo-analytics
#
# Uso:
#   powershell -File scripts\backup-workspace.ps1                     # zip no Desktop
#   powershell -File scripts\backup-workspace.ps1 -Destination "E:\"  # zip em outro lugar

param(
    # Desktop real do usuario (pode ser redirecionado pelo OneDrive)
    [string]$Destination = [Environment]::GetFolderPath('Desktop')
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyy-MM-dd'
$stage = Join-Path $env:TEMP "brabo-backup-$stamp"
$zip = Join-Path $Destination "brabo-backup-$stamp.zip"

if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

function Copy-Rel {
    param([string]$RelPath)
    $src = Join-Path $root $RelPath
    if (-not (Test-Path -LiteralPath $src)) {
        Write-Host "  (ausente, pulando) $RelPath"
        return
    }
    $dst = Join-Path $stage "workspace\$RelPath"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
    Write-Host "  + $RelPath"
}

Write-Host "Coletando segredos e configuracoes..."
Copy-Rel '.env'
Copy-Rel 'json'
Copy-Rel 'youtube\client_secrets.json'
Copy-Rel 'youtube\token_bb.json'
Copy-Rel '.claude\settings.local.json'

Write-Host "Coletando dados fora do git..."
Copy-Rel 'active-campaign'

# CSVs de analises/ (ignorados pelo git; contem PII — manter o zip privado)
Write-Host "Coletando CSVs de analises\..."
Get-ChildItem -LiteralPath (Join-Path $root 'analises') -Recurse -File -Filter *.csv | ForEach-Object {
    $rel = $_.FullName.Substring($root.Length + 1)
    $dst = Join-Path $stage "workspace\$rel"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $dst -Force
}
$csvCount = (Get-ChildItem -LiteralPath (Join-Path $stage 'workspace\analises') -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "  + $csvCount CSVs"

Write-Host "Coletando memoria do Claude Code..."
$claudeMem = Join-Path $env:USERPROFILE '.claude\projects\c--dev-workspace-mmm\memory'
if (Test-Path -LiteralPath $claudeMem) {
    Copy-Item -LiteralPath $claudeMem -Destination (Join-Path $stage 'claude-memory') -Recurse -Force
    Write-Host "  + claude-memory"
}

Write-Host "Registrando estado do git..."
$gitInfo = @(
    "remote : $(git -C $root remote get-url origin)"
    "branch : $(git -C $root rev-parse --abbrev-ref HEAD)"
    "commit : $(git -C $root rev-parse HEAD)"
    "status : $(git -C $root status -s | Out-String)"
    "user   : $(git -C $root config user.name) <$(git -C $root config user.email)>"
)
$gitInfo | Out-File (Join-Path $stage 'git-info.txt') -Encoding utf8

$restoreSrc = Join-Path $root 'documentacao\RESTAURAR_MAQUINA_NOVA.md'
if (Test-Path -LiteralPath $restoreSrc) {
    Copy-Item -LiteralPath $restoreSrc -Destination (Join-Path $stage 'LEIA-ME-RESTAURAR.md')
}

Write-Host "Compactando em $zip ..."
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path "$stage\*" -DestinationPath $zip -CompressionLevel Optimal
Remove-Item -LiteralPath $stage -Recurse -Force

$sizeMB = [Math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 1)
Write-Host ""
Write-Host "Backup concluido: $zip ($sizeMB MB)"
Write-Host "ATENCAO: o zip contem segredos (.env, chaves Google) e PII de leads."
Write-Host "Guarde em local privado (drive externo ou nuvem pessoal), nunca em repositorio."
