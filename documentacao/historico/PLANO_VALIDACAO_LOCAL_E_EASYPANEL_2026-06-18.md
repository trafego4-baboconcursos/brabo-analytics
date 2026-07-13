# Plano de Validacao Local e Deploy EasyPanel - 2026-06-18

## Objetivo

Consolidar o estado atual do projeto e transformar a evolucao feita em um plano operacional claro:

- validar 100% local antes de publicar;
- manter a V1 estatica como referencia historica;
- priorizar a V2 dinamica como app principal;
- preparar deploy online no EasyPanel com web app e ETL separados.

## Leitura de documentacao considerada

Foram considerados os documentos em `documentacao/`:

- `README_ANALISE.md`
- `HOW_TO_CONTINUE.md`
- `ATUALIZACAO_12_MAIO_2026.md`
- `EVOLUCAO_FRONTEND_08_JUN_2026.md`
- `EVOLUCAO_FRONTEND_09_JUN_2026.md`
- `EVOLUCOES_2026-06-17.md`
- `METODOLOGIA_EXTRACAO_DADOS.md`
- `STATUS_PBB_JUN_26_2026-06-16.md`
- `HANDOFF_CRIATIVOS_REUTILIZAVEL.md`
- `ANALISE_META_ADS_MMM.md`
- `ANALISE_GOOGLE_ADS_MMM.md`
- `ANALISE_LEADS_CONFRONTO_FINAL_V2.md`
- `VERIFICACAO_GOOGLE_ADS_[PES-JAN-26].md`
- `BRIEFING_BRABO.md`
- `PROMPT_SISTEMA_ANALISE_AUTO.md`
- `prompt_analise_lancamentos.md`
- `GUIA_IMPLEMENTACAO_SERVER_SIDE_TRACKING.md`
- `PLANO_GTM_SERVER_SIDE.md`
- `PENDENCIA_TIKTOK_API.md`
- `LP_BB_VERIFICACAO.md`
- `Plano Nav Menu Horizontal + Servidor com Senha`
- bases de calendario em CSV.

## Linha do tempo do produto

### V1

A V1 e a pasta `analises/`, com HTMLs estaticos e CSVs locais por lancamento.

Ela foi a primeira fonte validada de numeros, especialmente em:

- funil;
- criativos;
- vendas por criativo;
- analises Meta e Google;
- audiencias;
- comparativos.

A V1 continua importante como referencia historica e base de comparacao.

### V2

A V2 e o app FastAPI em `frontend/`.

O caminho atual da V2 e:

`Plataformas/API ou CSV historico -> ETL -> Supabase/Postgres -> FastAPI -> templates HTML`

Decisao atual:

- V2 vira o app principal.
- V1 fica disponivel para auditoria e comparacao.
- O comparador V1/V2 deve ajudar a validar discrepancias antes de evoluir mais a interface.

## Arquitetura atual desejada

### Web app

- Serviço: `brabo-web`
- Comando local/producao:
  - local: `.\.venv\Scripts\python.exe -m uvicorn frontend.app:app --host 127.0.0.1 --port 8030`
  - container: `uvicorn frontend.app:app --host 0.0.0.0 --port 8000`
- Funcao:
  - renderizar dashboards;
  - ler dados do Supabase;
  - exibir comparativos, funil, criativos, vendas, Typeform e audiencias.

### ETL

- Serviço: `brabo-etl`
- Comando:
  - `python etl/scheduler.py`
- Funcao:
  - consultar APIs periodicamente;
  - atualizar tabelas do Supabase;
  - manter janela movel recente;
  - registrar logs.

### Banco

Fonte principal: Supabase/Postgres.

Tabelas e fontes relevantes:

- `dim_lancamentos`
- `meta_ads_daily`
- `google_ads_daily`
- `active_campaign_leads`
- `typeform_respostas`
- tabelas de vendas Hotmart/TMB quando populadas pelo TI ou importadas.

Observacao: CSVs locais seguem como fallback, historico e fonte de importacao, mas nao devem ser o modelo final de producao.

## Regras de negocio consolidadas

### Lancamentos e produtos

- `PI`: INSS
- `PES`: TJ-SP / Escrevente
- `PBB`: Banco do Brasil

Menu e filtros devem respeitar essa hierarquia:

`Produto -> Lancamento -> Paginas/analises`

### UTM antiga e nova

Antes de `PES-MAI-26`, os lancamentos usam padrao antigo de UTM. Em muitos casos o criativo aparece em `utm_content`.

A partir de `PES-MAI-26`, o padrao novo e:

Meta:

```text
utm_source=facebook
utm_medium=paid_social
utm_campaign={{campaign.name}}
utm_content={{adset.name}}
utm_term={{ad.name}}
vk_source=paid_metaads
vk_ad_id={{ad.id}}
```

Google/YouTube:

```text
utm_source=google
utm_medium=cpc
utm_campaign={_campaignname}
utm_content={_adgroupname}
utm_term={_adname}
vk_source=paid_googleads
vk_ad_id={creative}
```

Regra pratica:

- para lancamentos antigos, procurar `ADxxx` em todas as UTMs, com peso historico para `utm_content`;
- para `PES-MAI-26` em diante, usar `utm_term` como campo principal do criativo;
- para Search, P-Max e Display, quando nao houver criativo em `utm_term`, usar `utm_campaign`, `utm_content` e nome da campanha para identificar origem.

### Vendas e receita

Regra Hotmart:

- normalizar email;
- tratar `Recuperador Inteligente`;
- quando for compra parcelada, considerar o valor total contratado, nao apenas parcela paga isolada;
- usar a parcela 1 como referencia temporal de entrada quando necessario.

Regra TMB:

- normalizar email;
- historicamente houve divergencia entre filtrar ou nao `Vigente`;
- para paridade com dashboards validados, documentar em cada tela qual regra foi usada.

Regra de atribuicao:

- cruzar compradores Hotmart + TMB com leads do Active Campaign por email;
- buscar AD/campanha em todas as UTMs disponiveis;
- separar vendas rastreadas e vendas sem UTM;
- expor percentual de vendas sem rastreio para auditoria.

### Criativos

Ranking principal:

- deve consolidar Meta + Google/YouTube pelo mesmo `ADxxx`;
- nao deve duplicar `ADxxx` e nome completo em colunas separadas quando o nome completo ja contem o codigo;
- deve exibir investimento, leads, CPL, CTR, CPM, vendas, faturamento e ROAS;
- Search, P-Max e Display devem ficar em tabela propria;
- ADs herdados de outros lancamentos devem trazer UTMs completas para diagnostico.

### Typeform

O Typeform evoluiu para:

- resolver forms dinamicamente por tag de lancamento;
- diferenciar pesquisa de captacao/projeto e pesquisa de alunos/compradores;
- usar metadata da API para reconstruir perguntas;
- gerar diagnosticos, perfil demografico, voz dos alunos, fatores de compra e ganchos de copy.

## Decisoes pendentes importantes

1. Regra `PRE-*`
   - `PRE-PBB-JUN-26` hoje pode ser agregado em `PBB-JUN-26` por regex.
   - Decidir se campanhas `PRE-*` entram no lancamento principal, viram lancamento separado ou ficam como pre-aquecimento.

2. Vendas no banco
   - `PBB-JUN-26` ainda estava aguardando TI popular Hotmart/TMB.
   - Sem vendas no banco, ROAS e CPA por venda ficam incompletos.

3. Scheduler em producao
   - O scheduler ja existe e rodou com sucesso, mas precisa virar servico persistente no servidor.

4. Autenticacao
   - O app nao deve ficar publico sem protecao.
   - Manter login/sessao no app ou proteger via EasyPanel/reverse proxy.

5. TikTok
   - Integracao futura via API oficial + ETL + tabela `tiktok_ads_daily`.
   - Nao iniciar antes de estabilizar V2, vendas e deploy.

6. GTM/server-side
   - Projeto separado de infraestrutura.
   - Importante para melhorar qualidade de tracking, mas nao e bloqueador da publicacao inicial da V2.

## Plano de validacao 100% local

### 1. Ambiente Python

- usar obrigatoriamente `.venv`;
- validar importacao de `frontend.app`;
- validar `sqlalchemy`, `psycopg2`, `fastapi`, `uvicorn`, `pandas`.

### 2. Variaveis de ambiente

Validar presenca, sem imprimir segredos:

- `SUPABASE_DB_URL`
- credenciais Active Campaign;
- credenciais Meta;
- credenciais Google Ads;
- credenciais Typeform.

### 3. Banco

Validar:

- conexao com Supabase;
- leitura de `dim_lancamentos`;
- existencia de dados para lancamentos chave:
  - `PBB-ABR-26`
  - `PES-MAI-26`
  - `PBB-JUN-26`
  - `PI-ABR-26`

### 4. App

Subir localmente em uma porta unica, preferencialmente `8030`.

Validar rotas principais com HTTP 200:

- `/`
- `/funil?launch_code=PBB-ABR-26`
- `/criativos?launch_code=PBB-ABR-26`
- `/criativos?launch_code=PES-MAI-26`
- `/vendas?launch_code=PBB-ABR-26`
- `/typeform?launch_code=PBB-ABR-26`
- `/comparativo-v1-v2?launch_code=PBB-ABR-26`
- `/meta-audiences?launch_code=PBB-ABR-26`
- `/google-audiences?launch_code=PBB-ABR-26`

### 5. ETL

Validar sem escrever no banco:

- compilacao dos scripts;
- carregamento de configuracao;
- existencia de variaveis;
- logs anteriores.

Para rodar ETL real, registrar que ele escreve no Supabase e consulta APIs externas.

### 6. Docker local

Antes do EasyPanel:

- validar `docker build`;
- subir container local;
- testar rotas no container;
- confirmar que as variaveis de ambiente entram corretamente.

## Plano EasyPanel

### Servico 1: `brabo-web`

- Build pelo `Dockerfile` do repositorio.
- Porta interna: `8000`.
- Comando:

```bash
uvicorn frontend.app:app --host 0.0.0.0 --port 8000
```

- Expor dominio HTTPS.
- Configurar variaveis de ambiente.
- Proteger acesso.

### Servico 2: `brabo-etl`

- Mesmo build do repositorio.
- Sem porta publica.
- Comando:

```bash
python etl/scheduler.py
```

- Reinicio automatico.
- Logs persistidos/visiveis no EasyPanel.

### Banco

- Supabase externo.
- Nao subir Postgres no EasyPanel nesta primeira fase.
- Garantir pooler/URL compativel com ambiente do servidor.

## Criterio de pronto para publicar

O app pode ir para EasyPanel quando:

- app local sobe via `.venv`;
- rotas principais respondem 200;
- banco Supabase responde;
- paginas chave renderizam sem erro;
- Docker build passa;
- container local sobe;
- variaveis de ambiente estao mapeadas;
- decisao minima de seguranca esta definida;
- ETL esta separado do web app.

## Ordem recomendada daqui em diante

1. [x] Rodar validacao local completa.
2. [x] Corrigir erros de rota/importacao/dados encontrados.
3. [x] Validar Docker local.
4. [ ] Melhorias visuais e de UX localmente (porta 8030).
5. [ ] Compartilhar para revisao via ngrok (URL publica temporaria sem deploy).
6. [ ] Validar Docker apos melhorias.
7. [ ] Subir `brabo-web` no EasyPanel.
8. [ ] Proteger app (definir `ADMIN_USERNAME` e `ADMIN_PASSWORD` nas vars do EasyPanel).
9. [ ] Subir `brabo-etl` no EasyPanel.
10. [ ] Validar logs do ETL e dados novos.
11. [ ] So depois evoluir novas fontes como TikTok/GTM.

## Resultado da validacao local em 2026-06-18

### Validado

- `.venv` possui dependencias principais:
  - FastAPI
  - Uvicorn
  - SQLAlchemy
  - psycopg2
  - pandas
  - requests
- Compilacao Python passou para:
  - `frontend/app.py`
  - `frontend/database_reader.py`
  - scripts principais de `etl/`
- `.env` possui variaveis para:
  - Supabase
  - Active Campaign
  - Meta Ads
  - Google Ads
  - Typeform
- Conexao com Supabase validada com acesso de rede liberado.
- `discover_launches()` retornou 12 lancamentos.
- Servidor local respondeu em:
  - `http://127.0.0.1:8030`
- Login local validado.
- Rotas autenticadas validadas com HTTP 200:
  - `/`
  - `/funil?launch_code=PBB-ABR-26`
  - `/criativos?launch_code=PBB-ABR-26`
  - `/criativos?launch_code=PES-MAI-26`
  - `/vendas?launch_code=PBB-ABR-26`
  - `/typeform?launch_code=PBB-ABR-26`
  - `/comparativo-v1-v2?launch_code=PBB-ABR-26`
  - `/meta-audiences?launch_code=PBB-ABR-26`
  - `/google-audiences?launch_code=PBB-ABR-26`
  - `/funil?launch_code=PI-ABR-26`
  - `/funil?launch_code=PBB-JUN-26`
- V1 estatica validada via FastAPI:
  - `/analises/[PBB-ABR-26]/ANALISE_FUNIL_[PBB-ABR-26].html`
- Validacao complementar apos correcoes:
  - `/leads?launch_code=PBB-ABR-26`
  - `/hotmart?launch_code=PBB-ABR-26`

### Observacoes

- Sem sessao autenticada, as rotas retornam a tela de login, como esperado.
- A conexao com Supabase falha dentro do sandbox sem permissao de rede, mas passa quando a rede e liberada.
- A porta local padronizada para validacao foi `8030`.
- A pagina de Leads tinha incompatibilidade de template: os grupos de UTM passaram a ser dicionarios com metricas, mas o template tratava o valor como numero puro.
- A pagina Hotmart precisava expor campos de compatibilidade no leitor atual:
  - `receita_bruta`
  - `receita_liquida`
  - `taxas`
  - `taxas_pct`
  - `pagamentos`
- Apos ajuste e reinicio do servidor, ambas as paginas passaram a responder HTTP 200.

### Docker local validado em 2026-06-18

Docker Desktop instalado via winget. Ajustes realizados:

- Criado `.dockerignore` excluindo `.venv`, `.env`, `analises/` (761MB), `data/`, `logs/`, arquivos temporarios e de analise.
- `img/` mantida no contexto (logos e favicon necessarios para a UI).
- `frontend/app.py`: mount de `/analises` tornou-se condicional (`if ANALISES_DIR.exists()`), permitindo que o container suba sem a pasta V1.
- `Dockerfile`: adicionado `RUN mkdir -p /app/analises` para garantir que a pasta exista dentro do container caso alguma logica a referencie.

Resultado do build:

```
Successfully built brabo-web:latest
```

Container iniciado na porta `8001` com `--env-file .env`. Rotas testadas com sessao autenticada (credenciais padrao):

| Rota | Status |
| :--- | ---: |
| `/` | 200 |
| `/funil?launch_code=PBB-ABR-26` | 200 |
| `/criativos?launch_code=PBB-ABR-26` | 200 |
| `/criativos?launch_code=PES-MAI-26` | 200 |
| `/vendas?launch_code=PBB-ABR-26` | 200 |
| `/typeform?launch_code=PBB-ABR-26` | 200 |
| `/comparativo-v1-v2?launch_code=PBB-ABR-26` | 200 |
| `/meta-audiences?launch_code=PBB-ABR-26` | 200 |
| `/google-audiences?launch_code=PBB-ABR-26` | 200 |
| `/leads?launch_code=PBB-ABR-26` | 200 |
| `/hotmart?launch_code=PBB-ABR-26` | 200 |

Todas as 11 rotas responderam HTTP 200 dentro do container.

### Pendente

- ETL real nao foi executado nesta validacao para evitar escrita no Supabase sem confirmacao explicita.
- Credenciais de acesso estao no padrao de desenvolvimento (`brabo` / `pbb2026`). Antes de publicar, configurar `ADMIN_USERNAME` e `ADMIN_PASSWORD` via variaveis de ambiente no EasyPanel.
- V1 (`/analises`) nao estara disponivel no container EasyPanel ate que um volume ou estrategia de persistencia seja definida (pasta de 761MB nao e incluida na imagem).

## Criterio de pronto — status atualizado

| Item | Status |
| :--- | :--- |
| App local sobe via `.venv` | Validado |
| Rotas principais respondem 200 local | Validado |
| Banco Supabase responde | Validado |
| Paginas chave renderizam sem erro | Validado |
| Docker build passa | Validado |
| Container local sobe | Validado |
| Variaveis de ambiente entram no container | Validado |
| Decisao minima de seguranca definida | Pendente |
| ETL separado do web app | Definido na arquitetura, deploy pendente |

**Proximo passo: subir `brabo-web` no EasyPanel.**
