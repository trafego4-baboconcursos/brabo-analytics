# Restaurar o Brabo Analytics em uma máquina nova

> Par deste guia: `scripts/backup-workspace.ps1` gera o zip `brabo-backup-AAAA-MM-DD.zip`
> com tudo que **não** está no GitHub. O código vem do clone; o zip repõe segredos e dados.

## 1. Instalar pré-requisitos

- **Git** — https://git-scm.com
- **Python 3.14** — https://python.org (marcar "Add to PATH")
- **ngrok** — https://ngrok.com/download (logar com a conta da equipe: `ngrok config add-authtoken ...`)
- **VS Code** (opcional) + extensão Claude Code

## 2. Clonar o repositório (fora do OneDrive!)

```powershell
git clone https://github.com/trafego4-baboconcursos/brabo-analytics C:\dev\workspace-mmm
cd C:\dev\workspace-mmm
git config user.name "Brabo Marketing"
git config user.email "trafego4@aprovasim.com"
```

> ⚠️ **Nunca dentro do OneDrive** — ele já corrompeu o `.git` uma vez.
> Usar `C:\dev\workspace-mmm` mantém os caminhos idênticos (memória do Claude, scripts).

## 3. Extrair o backup

Extrair o zip e copiar:

| Do zip | Para |
|---|---|
| `workspace\.env` | `C:\dev\workspace-mmm\.env` |
| `workspace\json\` | `C:\dev\workspace-mmm\json\` |
| `workspace\youtube\client_secrets.json` e `token_bb.json` | `C:\dev\workspace-mmm\youtube\` |
| `workspace\analises\` (CSVs) | `C:\dev\workspace-mmm\analises\` (mesclar com as pastas do clone) |
| `workspace\active-campaign\` | `C:\dev\workspace-mmm\active-campaign\` |
| `workspace\.claude\settings.local.json` | `C:\dev\workspace-mmm\.claude\settings.local.json` |
| `claude-memory\` | `C:\Users\<USUARIO>\.claude\projects\c--dev-workspace-mmm\memory\` |

> A pasta de memória do Claude é chaveada pelo **caminho do projeto** — se o projeto
> ficar em `C:\dev\workspace-mmm`, o slug é `c--dev-workspace-mmm`, igual ao atual.

## 4. Recriar o ambiente Python

```powershell
cd C:\dev\workspace-mmm
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 5. Subir e validar

```powershell
scripts\start-dev.ps1   # sobe uvicorn + scheduler ETL + ngrok
```

Checklist:
- [ ] `http://127.0.0.1:8000` abre a tela de login e o login funciona (banco operacional OK)
- [ ] Dashboard de um lançamento carrega dados (banco analytics OK)
- [ ] `etl\scheduler.log` mostra rodada de ETL sem erros (APIs Meta/Google OK)
- [ ] Thumbnails aparecem em /meta (service account Drive OK)
- [ ] `.venv\Scripts\python.exe -m pytest` — todos os testes passam

## 6. Extras (se usados na máquina antiga)

- **GitHub CLI**: `winget install GitHub.cli` e `gh auth login`
- **Claude Code**: instalar e abrir na pasta `C:\dev\workspace-mmm`
- Agendar o `scripts\start-dev.ps1` no boot, se desejado (Agendador de Tarefas do Windows)

## O que NÃO precisa de backup

- `.venv/`, `node_modules/`, `.next/`, `__pycache__/`, `.uv-cache/` — regeneráveis
- Código, templates, documentação — já no GitHub
- Dados do Supabase — ficam na nuvem (os dois bancos), nada é local
