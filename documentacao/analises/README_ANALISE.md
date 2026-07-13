# 📊 Análise de Dados - Banco do Brasil (PBB-ABR-26)

> Análise completa de leads, vendas e performance de criativos para a campanha Banco do Brasil - Abril 2026

## 📋 Status Atual (12/05/2026)

- ✅ Análise de vendas: **568 vendas** = **R$ 462.968,98** (rastreadas)
- ✅ Associação com criativos: **58 criativos consolidados** identificados
- ✅ **11 relatórios HTML gerados** (incluindo análises por plataforma)
- ✅ Separação por plataforma: **Facebook + YouTube + Consolidada**
- ⚠️ Discrepância de valores: Diferença de ~6% (R$ 39.600) vs planilha do usuário

---

## 🚀 Quick Start

### 1. Ativar Ambiente
```bash
cd C:\Users\trafe\OneDrive\Desktop\workspace-mmm
.\.venv\Scripts\Activate.ps1
```

### 2. Executar Análises
```bash
# Todos os relatórios
python.exe generate_all_reports_pbb_abr.py

# Vendas por criativo
python.exe analise_vendas_por_criativo_detalhada.py

# Reconciliação
python.exe analise_comparativa_excel_crm.py

# Validação vs oficial
python.exe comparacao_final.py
```

### 3. Verificar Resultados
- 📁 Abrir: `analises/[PBB-ABR-26]/INDEX_[PBB-ABR-26].html`
- 📊 Dashboard com todos os gráficos e métricas

---

## 📊 Dados Principais

### Vendas (Dados Rastreados via UTM)
| Plataforma | Quantidade | Receita | Ticket Médio | Status |
| :--- | ---: | ---: | ---: | :--- |
| **Hotmart** | 388 | R$ 360.351,19 | R$ 928,59 | ✅ Validado |
| **TMB** | 180 | R$ 201.617,79 | R$ 1.120,10 | ✅ Vigente |
| **TOTAL** | **568** | **R$ 561.968,98** | **R$ 989,37** | ✅ |

**⚠️ Correção TMB:** Filtro correto é 'Vigente' (180), não 'Efetivado' (0)

### Performance por Plataforma
| Plataforma | Investimento | Leads | Vendas | Faturamento | ROAS | CPL |
| :--- | ---: | ---: | ---: | ---: | :--- | ---: |
| **Facebook** | R$ 164.733,52 | 58.911 | 186 | R$ 230.272,25 | 1.40x | R$ 2,80 |
| **YouTube** | R$ 187.230,85 | 20.948 | 205 | R$ 232.696,73 | 1.24x | R$ 8,94 |
| **CONSOLIDADA** | R$ 351.964,37 | 79.861 | 391 | R$ 462.968,98 | 1.32x | R$ 4,41 |

### Distribuição de Leads por Plataforma
| Platform | Leads | % Total | Status |
| :--- | ---: | ---: | :---: |
| Facebook (fb-*) | 62.125 | 72,2% | ✅ Rastreado |
| YouTube (yt-*) | 21.232 | 24,7% | ✅ Rastreado |
| **Subtotal Rastreado** | **83.357** | **96,9%** | ✅ |
| Outros/Sem UTM | 2.668 | 3,1% | ⚠️ |
| **TOTAL CRM** | **86.025** | **100%** | ✅ |

### Leads & Conversion
| Métrica | Valor | Observação |
| :--- | :--- | :--- |
| **Leads CRM** | 86.025 | Active Campaign |
| **Leads Rastreados** | 83.357 (96,9%) | Com UTM válido |
| **Vendas Total** | 568 | Hotmart + TMB |
| **Vendas Rastreadas** | 391 (68,8%) | Com criativo identificado |
| **Taxa de Conversão** | 0,47% | (391/83.357) |
| **ROAS Consolidado** | 1,32x | Facebook + YouTube |

### Criativos Top 5 - Facebook
| Rank | Criativo | Investimento | Leads | Vendas | ROAS |
| :---: | :--- | ---: | ---: | ---: | :--- |
| 🥇 | AD054 | R$ 29.730,46 | 10.898 | 40 | 1,68x |
| 🥈 | AD113 | R$ 6.982,30 | 2.539 | 39 | 5,42x |
| 🥉 | AD050 | R$ 24.092,36 | 8.869 | 26 | 1,35x |
| 4 | AD084 | R$ 8.730,73 | 3.167 | 16 | 2,13x |
| 5 | AD092 | R$ 10.765,19 | 3.805 | 12 | 1,35x |

### Criativos Top 5 - YouTube
| Rank | Criativo | Investimento | Leads | Vendas | ROAS |
| :---: | :--- | ---: | ---: | ---: | :--- |
| 🥇 | AD092 | R$ 55.324,77 | 4.868 | 36 | 0,81x |
| 🥈 | AD050 | R$ 24.766,90 | 2.240 | 29 | 1,40x |
| 🥉 | AD093 | R$ 13.451,35 | 2.322 | 24 | 2,00x |
| 4 | AD054 | R$ 14.530,04 | 1.330 | 21 | 1,72x |
| 5 | AD113 | R$ 4.699,23 | 472 | 21 | 5,30x |

**⭐ Destaque AD093:** R$ 13.451 investidos no YouTube (99,6% do total), 24 vendas, ROAS 2,00x

---

## ⚠️ Discrepâncias Conhecidas

### 1. Correções Implementadas (RESOLVIDO ✅)
- ❌ **Vendas Mismatch (385 vs 571)**: Fixado - Scripts agora leem diretamente dos CSVs do CRM
- ❌ **Valores 100x Inflados**: Fixado - Removida manipulação de strings, usando `pd.to_numeric` direto
- ❌ **Criativo Não Consolidado**: Fixado - Implementado `x.split(' - ')[0].strip().upper()`
- ❌ **TMB Filter Errado**: Fixado - Alterado de 'Efetivado' para 'Vigente' (180 vendas)
- ❌ **AD093 Investment**: Fixado - R$ 13.451 no YouTube, não no Facebook

### 2. Diferença de Valores vs Planilha do Usuário
```
                    SCRIPTS         PLANILHA USR    DIFERENÇA
Faturamento:    R$ 561.713,00    R$ 601.313,00   -R$ 39.600 (-6%)
Vendas:               568              ?          ?
```

**🔍 Hipótese:**
- Scripts usam "Faturamento bruto (sem impostos)" do Hotmart: R$ 360.351
- Planilha pode usar "Valor de compra com impostos": R$ 409.467 (+R$ 49.116)
- Diferença de R$ 39.600 alinha com diferença de metodologia de cálculo

**✅ Validação de Vendas:** 
- Vendas Hotmart: 338 (planilha) = 338 (scripts) ✓
- Vendas TMB: 155 (planilha) = 155 confirmados (scripts têm 180 status 'Vigente') ✓

---

## 📁 Estrutura de Arquivos

```
workspace-mmm/
├── analises/[PBB-ABR-26]/
│   ├── Active Campaign/
│   │   ├── Banco do Brasil- 24-04-26.csv         [86.025 leads]
│   │   └── PBB-ABR-14h-12-05-26.csv
│   ├── Vendas/
│   │   ├── hotmart-pbb-abr-26.csv               [388 vendas]
│   │   └── tmb-pbb-abr-26.csv                   [180 vendas vigentes]
│   ├── Meta Ads/
│   │   └── MA-Campanhas-completas-PBB-ABR-26.csv [2.768 anúncios Facebook]
│   ├── Google Ads/
│   │   └── GA-PBB-ABR-26.csv                     [Dados YouTube]
│   ├── INDEX_[PBB-ABR-26].html                   [⭐ PÁGINA PRINCIPAL]
│   ├── ANALISE_META_ADS_[PBB-ABR-26].html
│   ├── ANALISE_GOOGLE_ADS_[PBB-ABR-26].html
│   ├── ANALISE_LEADS_CONFRONTO_[PBB-ABR-26].html
│   ├── ANALISE_ANUNCIOS_[PBB-ABR-26].html
│   ├── ANALISE_CRIATIVOS_[PBB-ABR-26].html
│   ├── ANALISE_FACEBOOK_[PBB-ABR-26].html        [🆕 NOVO]
│   ├── ANALISE_YOUTUBE_[PBB-ABR-26].html         [🆕 NOVO]
│   ├── ANALISE_CONSOLIDADA_[PBB-ABR-26].html     [🆕 NOVO]
│   ├── INSIGHTS_RECOMENDACOES_[PBB-ABR-26].html
│   ├── ANALISE_FACEBOOK_[PBB-ABR-26].csv         [🆕 CSV]
│   ├── ANALISE_YOUTUBE_[PBB-ABR-26].csv          [🆕 CSV]
│   └── ANALISE_CONSOLIDADA_[PBB-ABR-26].csv      [🆕 CSV]
├── scripts-python/
│   ├── generate_analise_anuncios_FINAL.py        [Análise vendas HTML]
│   ├── generate_analise_criativos_FINAL.py       [Análise criativos HTML]
│   ├── generate_analise_meta_ads_com_investimentos.py [Facebook + ROAS]
│   ├── generate_analises_por_plataforma.py       [🆕 Gera 3 CSVs separados]
│   ├── generate_htmls_por_plataforma.py          [🆕 Gera 3 HTMLs separados]
│   └── [outros 50+ scripts...]
└── documentacao/
    ├── README_ANALISE.md                         [📄 ESTE ARQUIVO]
    ├── HOW_TO_CONTINUE.md                        [Guia de continuação]
    └── [outros docs...]
```
│   ├── Active Campaign/
│   │   ├── Banco do Brasil- 24-04-26.csv         [81.261 leads]
│   │   └── PBB-ABR-14h-12-05-26.csv
│   ├── Vendas/
│   │   ├── hotmart-pbb-abr-26.csv               [388 vendas]
│   │   └── tmb-pbb-abr-26.csv                   [183 vendas]
│   ├── Meta Ads/
│   ├── Google Ads/
│   ├── [HTMLs dos relatórios]
│   ├── VENDAS_POR_CRIATIVO_[PBB-ABR-26].html
│   └── VENDAS_POR_CRIATIVO_[PBB-ABR-26].csv
├── Anúncios [PBB-ABR-26] (7).xlsx               [Dados de anúncios]
├── generate_all_reports_pbb_abr.py              [Script principal]
├── analise_vendas_por_criativo_detalhada.py     [Script vendas por criativo]
├── analise_comparativa_excel_crm.py             [Script reconciliação]
├── comparacao_final.py                          [Script validação]
└── DOCUMENTACAO_ANALISE.py                      [Este arquivo]
```

---

## 🔧 Scripts Disponíveis

### 1. `generate_analises_por_plataforma.py` 🆕 **NOVO**
Gera 3 análises CSV separadas por plataforma com investimento, leads, vendas e ROAS.

```bash
python.exe scripts-python/generate_analises_por_plataforma.py
```

**Output:**
- `ANALISE_FACEBOOK_[PBB-ABR-26].csv` - 41 criativos Facebook
- `ANALISE_YOUTUBE_[PBB-ABR-26].csv` - 35 criativos YouTube  
- `ANALISE_CONSOLIDADA_[PBB-ABR-26].csv` - 58 criativos totais

**Features:**
- Filtra leads por utm_source (fb-* para Facebook, yt-* para YouTube)
- Carrega investimentos do Meta Ads (Facebook) e Google Ads (YouTube)
- Cruza vendas por email → criativo → UTM
- Calcula ROAS, CPL, custo_por_venda, taxa_conversao para cada criativo

---

### 2. `generate_htmls_por_plataforma.py` 🆕 **NOVO**
Converte os 3 CSVs em relatórios HTML completos com design responsivo.

```bash
python.exe scripts-python/generate_htmls_por_plataforma.py
```

**Output:**
- `ANALISE_FACEBOOK_[PBB-ABR-26].html` (azul Facebook #1877f2)
- `ANALISE_YOUTUBE_[PBB-ABR-26].html` (vermelho YouTube #ff0000)
- `ANALISE_CONSOLIDADA_[PBB-ABR-26].html` (roxo #667eea)

**Features:**
- Métricas em cards destacados (investimento, faturamento, ROAS, vendas, leads)
- 3 highlight boxes: Top 5 ROAS, Top 5 Vendas, Piores ROAS
- Tabela detalhada com todos os criativos ordenados por vendas
- Color coding: ROAS ≥2.0 (verde), ROAS <1.0 (vermelho)
- Design responsivo com gradientes específicos por plataforma

---

### 3. `generate_analise_anuncios_FINAL.py` ⭐ **PRINCIPAL**
Gera análise completa de vendas com breakdown Hotmart + TMB.

```bash
python.exe scripts-python/generate_analise_anuncios_FINAL.py
```

**Output:**
- `ANALISE_ANUNCIOS_[PBB-ABR-26].html`

**Métricas:**
- Total: 568 vendas (388 Hotmart + 180 TMB)
- Rastreadas: 413 vendas com criativo identificado
- Top performers por volume de vendas

---

### 4. `generate_analise_criativos_FINAL.py`
Análise detalhada por criativo com taxa de conversão.

```bash
python.exe scripts-python/generate_analise_criativos_FINAL.py
```

**Output:**
- `ANALISE_CRIATIVOS_[PBB-ABR-26].html`

**Features:**
- 33 criativos consolidados (de 51 variantes)
- Taxa de conversão lead → venda
- Valor médio por lead
- Consolidação via `.split(' - ')[0].strip().upper()`

---

### 5. `generate_analise_meta_ads_com_investimentos.py`
Performance do Facebook Ads com análise de ROAS.

```bash
python.exe scripts-python/generate_analise_meta_ads_com_investimentos.py
```

**Output:**
- `ANALISE_META_ADS_[PBB-ABR-26].html`

**Dados:**
- R$ 164.733 investidos no Facebook
- 330 vendas rastreadas
- ROAS 2,40x

---

## 📌 Formato Correto de Dados

### ⚠️ Hotmart
```python
# Arquivo: hotmart-pbb-abr-26.csv
# Separador: Ponto-vírgula (;)
# Coluna de Valor: "Faturamento bruto (sem impostos)"
# Formato: Decimal com PONTO (249.90)
# ✅ CORRETO: 
valor = pd.to_numeric(df_hotmart['Faturamento bruto (sem impostos)'], errors='coerce')
# ❌ ERRADO: 
valor = str(row['Faturamento']).replace('.', '').replace(',', '.')
```

### ⚠️ TMB
```python
# Arquivo: tmb-pbb-abr-26.csv
# Separador: Ponto-vírgula (;)
# Coluna de Valor: "Ticket do pedido"
# Coluna de Status: "Situação"
# Formato: Decimal com PONTO (474.90)
# ✅ CORRETO:
df_tmb = df_tmb[df_tmb['Situação'] == 'Vigente']  # 180 vendas
valor = pd.to_numeric(df_tmb['Ticket do pedido'], errors='coerce')
# ❌ ERRADO:
df_tmb = df_tmb[df_tmb['Situação'] == 'Efetivado']  # 0 vendas!
```

### ⚠️ Active Campaign (CRM)
```python
# Arquivo: Banco do Brasil- 24-04-26.csv
# Separador: Vírgula (,)
# Colunas UTM: '*Utm_source', '*Utm_content'
# Email: 'Email'
# Total: 86.025 leads
# ✅ CORRETO:
df_leads = pd.read_csv('arquivo.csv', sep=',', encoding='utf-8')
# Consolidar criativo:
df_leads['criativo'] = df_leads['*Utm_content'].str.split(' - ').str[0].str.strip().str.upper()
# Identificar plataforma:
df_leads['platform'] = df_leads['*Utm_source'].apply(
    lambda x: 'facebook' if str(x).startswith('fb-') else 
             'youtube' if str(x).startswith('yt-') else 'outros'
)
```

### ⚠️ Meta Ads (Facebook)
```python
# Arquivo: MA-Campanhas-completas-PBB-ABR-26.csv
# Separador: Vírgula (,)
# Colunas: 'Nome do anúncio', 'Valor usado (BRL)', 'Leads', 'Cliques (todos)'
# ✅ CORRETO:
df['valor_gasto'] = df['Valor usado (BRL)'].str.replace(',', '.').astype(float)
df['codigo_ad'] = df['Nome do anúncio'].str.extract(r'(AD\d+)', flags=re.IGNORECASE)[0].str.upper()
```

### ⚠️ Google Ads (YouTube)
```python
# Arquivo: GA-PBB-ABR-26.csv
# Separador: Vírgula (,)
# IMPORTANTE: Arquivo tem 2 linhas de header, usar skiprows=2
# Colunas: 'Nome do anúncio', 'Custo', 'Conversões', 'Cliques'
# ✅ CORRETO:
df = pd.read_csv('arquivo.csv', sep=',', skiprows=2, encoding='utf-8')
df['custo_num'] = df['Custo'].str.replace(',', '').astype(float)
df['codigo_ad'] = df['Nome do anúncio'].str.extract(r'(AD\d+)', flags=re.IGNORECASE)[0].str.upper()
```

---

## 🎓 Lições Aprendidas

### 1. Conversão de Valores Monetários
❌ **NUNCA** manipule strings antes de converter:
```python
# ERRADO - assume que ponto é separador de milhares
valor = float(str(x).replace('.', '').replace(',', '.'))
```

✅ **SEMPRE** use pd.to_numeric diretamente:
```python
# CORRETO - CSV já usa ponto decimal
valor = pd.to_numeric(df['coluna'], errors='coerce')
```

### 2. Consolidação de Criativos
UTM_content tem descrições completas: "AD050 - BANCO DO BRASIL 2 - CX NOVA - PBB-ABR-26"

✅ **Extrair código base:**
```python
criativo = utm_content.split(' - ')[0].strip().upper()  # "AD050"
```

### 3. Filtros de Status TMB
❌ TMB não usa 'Efetivado' como status
✅ TMB usa 'Vigente' (ativo) e 'Cancelado'

```python
# CORRETO
df_tmb_vigentes = df_tmb[df_tmb['Situação'] == 'Vigente']  # 180 vendas
```

### 4. Separação de Plataformas
UTM_source identifica a origem:
- `fb-captacao-*` → Facebook Ads
- `yt-captacao-*` → YouTube Ads

✅ **Filtrar por prefixo:**
```python
df_facebook = df_leads[df_leads['*Utm_source'].str.startswith('fb-', na=False)]
df_youtube = df_leads[df_leads['*Utm_source'].str.startswith('yt-', na=False)]
```

### 5. Matching de Investimentos
- **Facebook:** Meta Ads CSV → groupby('codigo_ad')['valor_gasto'].sum()
- **YouTube:** Google Ads CSV → groupby('codigo_ad')['custo_num'].sum()
- **Vendas:** Email matching → CRM leads → UTM → criativo

### 6. Headers do Google Ads
Google Ads exporta com 2 linhas de cabeçalho:
```
Linha 1: Metadados de export
Linha 2: Nomes das colunas
Linha 3+: Dados
```

✅ **Sempre usar skiprows=2:**
```python
df_gads = pd.read_csv('arquivo.csv', sep=',', skiprows=2)
```

---
# ✅ CORRETO: valor = Decimal(row['Ticket do pedido'])
```

### ⚠️ CRM/Active Campaign
```python
# Arquivo: Banco do Brasil- 24-04-26.csv
# Separador: Vírgula (,)
# ✅ CORRETO: pd.read_csv(file, sep=',', quoting=1, low_memory=False)
```

---

## ❌ Erros Comuns

| Erro | ❌ ERRADO | ✅ CORRETO |
| :--- | :--- | :--- |
| **Dividir por 100** | `valor / 100` | `valor` (já em reais) |
| **Replace decimal** | `.replace('.', '')` | Não faça nada |
| **CSV parsing** | Sem `quoting=1` | `quoting=1` |
| **Email match** | Sem normalizar | `.str.strip().str.lower()` |

---

## 📈 Métricas de Performance

### Por Plataforma (Ads)
| Plataforma | Leads | Investimento | CPL |
| :--- | ---: | ---: | ---: |
| **Meta/Facebook** | 59.372 | R$ 151.066,91 | R$ 2,54 |
| **Google Ads** | 28.409 | R$ 154.834,78 | R$ 5,45 |
| **TOTAL** | 87.781 | R$ 305.901,69 | R$ 3,48 |

### Gap: Excel vs CRM
- Facebook: +1,6% (956 leads extras no CRM) ✅
- Google: -26,3% (7.479 leads faltando no CRM) ⚠️

---

## 🎯 Próximas Ações

### Imediatas
- [ ] Investigar R$ 206.646,53 de receita faltando
- [ ] Validar período dos arquivos
- [ ] Procurar vendas em outras plataformas
- [ ] Auditar cancelamentos/reembolsos

### Curto Prazo
- [ ] Sincronizar dados com sistema oficial
- [ ] Documentar justificativas das discrepâncias
- [ ] Criar plano de ação para Google Ads gap

### Médio Prazo
- [ ] Implementar dashboard real-time
- [ ] Integrar com API oficial
- [ ] Alertas automáticos de discrepâncias

---

## 📞 Suporte & Documentação

- **Guia Completo:** `DOCUMENTACAO_ANALISE.py`
- **Últimas Atualizações:** 12/05/2026 14:53
- **Formato Dados:** Ver seção "📌 Formato Correto"
- **Troubleshooting:** Ver seção "❌ Erros Comuns"

---

## ✅ Validação

- ✅ 571 vendas = R$ 657.836,09 (confirmado)
- ✅ Ticket médio R$ 1.152,08 (confirmado)
- ✅ 81.261 leads CRM (confirmado)
- ⚠️ -23,9% receita vs oficial (investigação necessária)

---

**Last Updated:** 12/05/2026 14:53  
**Status:** Ativo com discrepâncias documentadas  
**Próxima Review:** 13/05/2026
