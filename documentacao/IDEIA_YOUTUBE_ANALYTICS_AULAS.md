# YouTube Analytics — Engajamento das Aulas

**Status:** Implementado e funcional (views). Watch time/retenção dependem de token do dono do canal.

---

## O que foi implementado

### Arquivos
- `etl/get_youtube_token.py` — gera o `YOUTUBE_REFRESH_TOKEN` (OAuth local ou remoto via `--gerar-url`)
- `etl/etl_youtube_analytics.py` — ETL completo: YouTube Data API + Analytics API → banco
- `frontend/database_reader.py` — `read_youtube_aulas(launch_code)` → `list[YoutubeAulaStat]`
- `frontend/templates/debriefing.html` — seção "Engajamento das Aulas" com dados reais

### Dados por fonte
| Fonte | Dados |
|---|---|
| YouTube Data API v3 | views totais, likes, comentários, duração do vídeo, pico simultâneo (live) |
| YouTube Analytics API | watch time total, duração média assistida, % retenção, split views ao vivo vs replay |

---

## Limitação crítica — YouTube Analytics API

**A YouTube Analytics API só aceita autenticação do dono do canal.**

Acesso de gestor via YouTube Studio **não funciona** para o OAuth. Mesmo sendo gestor, o token gerado será do seu canal pessoal (ex: "Brabo Editora"), não do canal gerenciado (ex: "Felipe Graton"). A API retorna linhas vazias sem erro.

### Canais e responsáveis

| Produto | Canal | Responsável | Variável no .env |
|---|---|---|---|
| PBB | Felipe Graton (`UCc4HH365cSFhzCzIPFRg2ag`) | Felipe Graton | `YOUTUBE_REFRESH_TOKEN` |
| PES | Ivan Neto / Brabo Concursos | Ivan Neto | `YOUTUBE_REFRESH_TOKEN_PES` |
| PI | Mateus Andrade | Mateus Andrade | `YOUTUBE_REFRESH_TOKEN_PI` |

> Cada responsável precisa autorizar o app **uma única vez** via fluxo remoto abaixo.

---

## Credenciais OAuth

- **Projeto GCP:** `youtube-analytics-501311`
- **Arquivo:** `youtube/client_secrets.json` (client_id: `989127753523-...`)
- **Escopos:** `youtube.readonly` + `yt-analytics.readonly`

> O projeto anterior (`youtube-descricoes`) usava escopo `youtube.force-ssl` (para editar descrições via `youtube/atualizar_bb.py`). São projetos e tokens separados.

---

## Como configurar um novo canal

### Opção A — O responsável está presente (presencial/call)

```bash
# Apagar token anterior se existir
# Edite o .env e deixe YOUTUBE_REFRESH_TOKEN= (vazio)

.venv\Scripts\python etl/get_youtube_token.py
```
Navegador abre → responsável loga com a **conta Google do canal dele** → autoriza → token salvo.

### Opção B — Fluxo remoto (sem acesso às credenciais)

**Passo 1 — Gerar URL e enviar ao responsável**
```bash
.venv\Scripts\python etl/get_youtube_token.py --gerar-url
```
Copie a URL gerada e envie por WhatsApp/email com estas instruções:

> "Abre esse link no navegador, faz login com a sua conta Google do YouTube, autoriza o acesso.
> O navegador vai abrir uma página de erro — é normal. Copia a URL completa da barra de endereço e me manda."

**Passo 2 — Receber a URL e salvar o token**
```bash
.venv\Scripts\python etl/get_youtube_token.py --trocar-codigo "http://localhost:8081/?code=4/0Ax..."
```
Token salvo automaticamente no `.env`.

---

## Como rodar o ETL

### Passo 1 — Adicionar vídeos no YAML do lançamento

`config/launches/pbb-jun-26.yaml`:
```yaml
youtube:
  aulas:
    - id: "GQ8ZP1qv9jM"
      label: "Aula 1 — 08/06"
    - id: "7RHcc7Oy22o"
      label: "Aula 2 — 09/06"
```
O `id` está na URL do YouTube: `youtube.com/watch?v=VIDEO_ID` ou `youtube.com/live/VIDEO_ID`.

As datas são lidas do campo `launch.date_range` do mesmo YAML.

### Passo 2 — Rodar

```bash
.venv\Scripts\python etl/etl_youtube_analytics.py --launch-code PBB-JUN-26
```

Para forçar período:
```bash
.venv\Scripts\python etl/etl_youtube_analytics.py --launch-code PBB-JUN-26 --start-date 2026-06-08 --end-date 2026-06-15
```

### Verificar o que foi salvo

```bash
.venv\Scripts\python -c "
import sys; sys.path.insert(0, 'src')
from dotenv import load_dotenv; load_dotenv()
from frontend.db import _get_engine
from sqlalchemy import text
with _get_engine().connect() as conn:
    rows = conn.execute(text(
        \"SELECT aula_num, titulo, views_total, watch_time_min, avg_view_pct, peak_concurrent \"
        \"FROM youtube_aulas_stats WHERE launch_code = 'PBB-JUN-26' ORDER BY aula_num\"
    )).fetchall()
    for r in rows:
        print(r)
"
```

---

## Dependência Python adicional

```bash
.venv\Scripts\pip install isodate
```

---

## Status por lançamento (2026-07-03)

| Lançamento | Views | Watch time / Retenção | Token |
|---|---|---|---|
| PBB-JUN-26 | ✅ 65.248 | ❌ aguardando token do Felipe | Pendente (Opção B) |
| PES-MAI-26 | ❌ sem vídeos no YAML | ❌ | Pendente (Ivan) |
| PI | ❌ sem vídeos no YAML | ❌ | Pendente (Mateus) |
