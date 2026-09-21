## Frontend local (FastAPI)

Rodar local:

```bash
python -m uvicorn frontend.app:app --reload
```

Depois acessar:
`http://127.0.0.1:8000`

Pré-requisitos:
- Python instalado
- Dependências: `fastapi`, `uvicorn`, `jinja2`

> Ao rodar a suíte de testes ou subir o app apontando para o `.env` de produção, use
> `PRE_WARM_CACHE=false` — sem isso o aquecimento reescreve `debriefing_snapshot` no banco
> real com números calculados pelo código do seu checkout.

## Onde fica o quê

| pasta | o que tem |
|---|---|
| `app.py` | cria o FastAPI, middlewares (auth, headers, gzip), mounts, startup |
| `core.py` | contexto base das páginas, sessão, filtros e globals do Jinja |
| `routes/` | as rotas, uma por domínio |
| `db_readers/` | todas as queries, um módulo por domínio |
| `services/` | regra de negócio entre a query e a página |
| `templates/` | os Jinja, um por página; `base.html` é o esqueleto herdado por todos |
| `static/` | **CSS e JS do design system** — servidos em `/static` |

## `static/` — o design system

Até 21/09/2026 tudo isso era inline no `base.html` (1.827 linhas de CSS + 2.343 de JS, num
arquivo de 5.053). Hoje são 16 arquivos; o `base.html` ficou só com markup.

**A ordem em que o `base.html` carrega estes arquivos é contrato** — é a cascata do CSS e a
ordem de dependência do JS. Os `<script>` são síncronos de propósito (sem `defer`/`async`).
Antes de renomear, reordenar ou juntar qualquer um, ler o comentário no `<head>` do
`base.html` e a seção "Onde estão as coisas" em `docs/sistema/DESIGN_SYSTEM.md`.

Ao adicionar um arquivo novo, referencie-o sempre por `{{ static_url('css/x.css') }}` — o
helper (em `core.py`) anexa `?v=<mtime>`, sem o qual o navegador serve a versão antiga depois
do deploy.

Duas coisas continuam inline no `base.html` de propósito: o `<style id="brabo-accent">`
(depende de `{{ accent }}`, a cor do lançamento) e o script anti-flash do tema no `<head>`
(precisa rodar antes do primeiro paint).
