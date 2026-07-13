# 📋 Atualização - 12 de Maio de 2026

## 🎯 Resumo Executivo

Implementada **separação completa por plataforma** para a campanha PBB-ABR-26, gerando análises individuais de Facebook e YouTube com investimento, vendas e ROAS por criativo.

---

## ✅ O Que Foi Implementado

### 1. Análises por Plataforma (CSVs)
**Script:** `generate_analises_por_plataforma.py`

Gerados 3 arquivos CSV completos:
- `ANALISE_FACEBOOK_[PBB-ABR-26].csv` - 41 criativos
- `ANALISE_YOUTUBE_[PBB-ABR-26].csv` - 35 criativos
- `ANALISE_CONSOLIDADA_[PBB-ABR-26].csv` - 58 criativos totais

**Metodologia:**
1. **Filtro de Leads por UTM_source:**
   - Facebook: `utm_source` começando com `fb-*`
   - YouTube: `utm_source` começando com `yt-*`

2. **Carga de Investimentos:**
   - Facebook: Meta Ads CSV (`MA-Campanhas-completas-PBB-ABR-26.csv`)
   - YouTube: Google Ads CSV (`GA-PBB-ABR-26.csv`, **skiprows=2**)

3. **Matching de Vendas:**
   - Email do CRM → Leads com UTM → Criativo → Plataforma
   - Hotmart: 'Email do(a) Comprador(a)'
   - TMB: 'E-mail do Cliente' + filtro 'Vigente'

4. **Cálculo de Métricas:**
   - ROAS = faturamento / investimento
   - CPL = investimento / leads
   - custo_por_venda = investimento / vendas
   - taxa_conversao = (vendas / leads) * 100

---

### 2. Relatórios HTML por Plataforma
**Script:** `generate_htmls_por_plataforma.py`

Gerados 3 relatórios HTML completos com design responsivo:
- `ANALISE_FACEBOOK_[PBB-ABR-26].html` (cor: azul Facebook #1877f2)
- `ANALISE_YOUTUBE_[PBB-ABR-26].html` (cor: vermelho YouTube #ff0000)
- `ANALISE_CONSOLIDADA_[PBB-ABR-26].html` (cor: roxo #667eea)

**Estrutura de Cada HTML:**

1. **Header com Logo e Título**
   - Branding da campanha
   - Data de geração

2. **Grid de Métricas (6 cards):**
   - 💰 Investimento Total
   - 💵 Faturamento CRM
   - 📊 ROAS Médio
   - 📈 Total de Vendas
   - 👥 Total de Leads
   - 💸 Custo por Lead

3. **3 Highlight Boxes:**
   - 🏆 Top 5 por ROAS
   - 📈 Top 5 por Vendas
   - ⚠️ Piores ROAS (atenção)

4. **Tabela Detalhada:**
   - Todos os criativos ordenados por vendas
   - Colunas: Investimento, Leads, Vendas, Faturamento, ROAS, CPL, Custo/Venda, Taxa Conversão
   - Top 3 destacados em amarelo
   - ROAS color-coded: verde ≥2.0, vermelho <1.0

5. **Resumo Consolidado:**
   - Estatísticas gerais da plataforma
   - Explicação das métricas

---

### 3. Atualização do INDEX
**Arquivo:** `INDEX_[PBB-ABR-26].html`

Adicionados 3 novos cards ao painel principal:
- 📘 **Análise Facebook** (link azul)
- 📺 **Análise YouTube** (link vermelho)
- 📊 **Análise Consolidada** (link roxo)

Total de análises no INDEX: **10 relatórios**

---

## 📊 Resultados Obtidos

### Performance por Plataforma

| Métrica | Facebook | YouTube | Consolidada |
| :--- | ---: | ---: | ---: |
| **Investimento** | R$ 164.733,52 | R$ 187.230,85 | R$ 351.964,37 |
| **Leads** | 58.911 | 20.948 | 79.861 |
| **Vendas** | 186 | 205 | 391 |
| **Faturamento** | R$ 230.272,25 | R$ 232.696,73 | R$ 462.968,98 |
| **ROAS** | **1,40x** | **1,24x** | **1,32x** |
| **CPL** | R$ 2,80 | R$ 8,94 | R$ 4,41 |
| **Taxa Conversão** | 0,32% | 0,98% | 0,49% |

### Distribuição de Leads

| Origem | Leads | % Total |
| :--- | ---: | ---: |
| Facebook (fb-*) | 62.125 | 72,2% |
| YouTube (yt-*) | 21.232 | 24,7% |
| Outros/Sem UTM | 2.668 | 3,1% |
| **TOTAL CRM** | **86.025** | **100%** |

### Top Criativos - Facebook

| Rank | Criativo | Investimento | Vendas | ROAS |
| :---: | :--- | ---: | ---: | :--- |
| 🥇 | AD054 | R$ 29.730,46 | 40 | 1,68x |
| 🥈 | AD113 | R$ 6.982,30 | 39 | 5,42x |
| 🥉 | AD050 | R$ 24.092,36 | 26 | 1,35x |

### Top Criativos - YouTube

| Rank | Criativo | Investimento | Vendas | ROAS |
| :---: | :--- | ---: | ---: | :--- |
| 🥇 | AD092 | R$ 55.324,77 | 36 | 0,81x |
| 🥈 | AD050 | R$ 24.766,90 | 29 | 1,40x |
| 🥉 | AD093 | R$ 13.451,35 | 24 | 2,00x |

---

## 🔍 Insights Principais

### 1. **Facebook: Alto Volume, ROAS Moderado**
- Responde por 72% dos leads (62.125)
- CPL mais baixo (R$ 2,80)
- ROAS 1,40x - acima do YouTube
- AD113 destaque: ROAS 5,42x com apenas R$ 6.982 investidos

### 2. **YouTube: Volume Menor, Conversão Melhor**
- 25% dos leads (21.232)
- CPL mais alto (R$ 8,94)
- ROAS 1,24x - abaixo do Facebook
- Taxa de conversão lead→venda **3x maior** (0,98% vs 0,32%)
- AD093: Investimento concentrado no YouTube (99,6%), ROAS 2,00x

### 3. **AD093: Caso de Estudo**
- **Problema:** Usuário relatou investimento de R$ 10k+, análise inicial mostrava R$ 59
- **Causa:** AD093 era quase 100% YouTube, análise estava olhando apenas Facebook
- **Solução:** Separação por plataforma revelou R$ 13.451 no YouTube
- **Resultado:** 24 vendas, ROAS 2,00x - criativo validado como eficiente

### 4. **Consolidação de Criativos**
- 51 variantes originais → 33 códigos base consolidados
- Método: `.split(' - ')[0].strip().upper()` extrai código (ex: "AD050")
- Permite análise consistente cross-platform

---

## 🛠️ Correções Técnicas Implementadas

### 1. **Valores Monetários (CRÍTICO)**
```python
# ❌ ANTES (ERRADO - valores 100x inflados)
valor = float(str(row['Faturamento']).replace('.', '').replace(',', '.'))

# ✅ AGORA (CORRETO)
valor = pd.to_numeric(df['Faturamento bruto (sem impostos)'], errors='coerce')
```

**Problema:** Scripts assumiam que ponto era separador de milhares  
**Realidade:** CSVs usam ponto como decimal (formato literal)

---

### 2. **Filtro TMB Status**
```python
# ❌ ANTES (0 vendas)
df_tmb[df_tmb['Situação'] == 'Efetivado']

# ✅ AGORA (180 vendas)
df_tmb[df_tmb['Situação'] == 'Vigente']
```

**Problema:** TMB não usa 'Efetivado' como status  
**Solução:** Filtrar por 'Vigente' (vendas ativas)

---

### 3. **Google Ads Header**
```python
# ❌ ANTES (erro de parse)
df = pd.read_csv('GA-PBB-ABR-26.csv', sep=',')

# ✅ AGORA (correto)
df = pd.read_csv('GA-PBB-ABR-26.csv', sep=',', skiprows=2)
```

**Problema:** Google Ads exporta com 2 linhas de header  
**Solução:** Usar `skiprows=2` para pular metadados

---

### 4. **Consolidação de Criativos**
```python
# ❌ ANTES (51 variantes separadas)
df_crm['criativo'] = df_crm['*Utm_content']

# ✅ AGORA (33 códigos consolidados)
df_crm['criativo'] = df_crm['*Utm_content'].str.split(' - ').str[0].str.strip().str.upper()
```

**Problema:** UTM_content tinha descrições completas ("AD050 - BANCO DO BRASIL 2 - CX NOVA")  
**Solução:** Extrair apenas código base (AD050)

---

### 5. **Separação de Plataformas**
```python
# ✅ NOVO - Identificar plataforma por UTM_source
df_leads['platform'] = df_leads['*Utm_source'].apply(
    lambda x: 'facebook' if str(x).startswith('fb-') else 
             'youtube' if str(x).startswith('yt-') else 'outros'
)

# Filtros específicos
df_facebook = df_leads[df_leads['*Utm_source'].str.startswith('fb-', na=False)]
df_youtube = df_leads[df_leads['*Utm_source'].str.startswith('yt-', na=False)]
```

**Inovação:** Permite análise independente de cada canal  
**Benefício:** ROAS, CPL e performance corretos por plataforma

---

## 📁 Novos Arquivos Criados

### Scripts Python
```
scripts-python/
├── generate_analises_por_plataforma.py    [🆕 319 linhas]
└── generate_htmls_por_plataforma.py       [🆕 287 linhas]
```

### Arquivos de Dados (CSV)
```
analises/[PBB-ABR-26]/
├── ANALISE_FACEBOOK_[PBB-ABR-26].csv      [🆕 41 criativos]
├── ANALISE_YOUTUBE_[PBB-ABR-26].csv       [🆕 35 criativos]
└── ANALISE_CONSOLIDADA_[PBB-ABR-26].csv   [🆕 58 criativos]
```

### Relatórios HTML
```
analises/[PBB-ABR-26]/
├── ANALISE_FACEBOOK_[PBB-ABR-26].html     [🆕 ~45KB]
├── ANALISE_YOUTUBE_[PBB-ABR-26].html      [🆕 ~42KB]
└── ANALISE_CONSOLIDADA_[PBB-ABR-26].html  [🆕 ~48KB]
```

### Documentação
```
documentacao/
└── ATUALIZACAO_12_MAIO_2026.md            [🆕 ESTE ARQUIVO]
```

---

## 🎯 Próximos Passos Recomendados

### Imediatos
- [ ] Revisar relatórios HTML com stakeholders
- [ ] Validar métricas de ROAS por criativo
- [ ] Confirmar se discrepância de R$ 39.600 é aceitável (hipótese: diferença entre "com impostos" vs "sem impostos")

### Curto Prazo (PBB-FEV-26)
- [ ] Aplicar mesma metodologia na campanha PBB-FEV-26
- [ ] Executar `generate_analises_por_plataforma.py` para FEV-26
- [ ] Gerar HTMLs comparativos ABR vs FEV

### Médio Prazo
- [ ] Automatizar geração de relatórios mensais
- [ ] Criar dashboard consolidado de todas as campanhas
- [ ] Implementar alertas de ROAS abaixo de 1.0x

### Melhorias Técnicas
- [ ] Adicionar gráficos interativos (Chart.js ou Plotly)
- [ ] Exportar para PDF automático
- [ ] Criar API para consulta de métricas em tempo real

---

## 📚 Referências

### Arquivos-Chave
- **README_ANALISE.md** - Documentação principal atualizada
- **GUIA_ANALISE_PBB.md** - Guia técnico completo (/memories/repo/)
- **HOW_TO_CONTINUE.md** - Instruções de continuação

### Dados de Origem
- Active Campaign: `Banco do Brasil- 24-04-26.csv` (86.025 leads)
- Hotmart: `hotmart-pbb-abr-26.csv` (388 vendas)
- TMB: `tmb-pbb-abr-26.csv` (180 vendas vigentes)
- Meta Ads: `MA-Campanhas-completas-PBB-ABR-26.csv` (2.768 anúncios)
- Google Ads: `GA-PBB-ABR-26.csv` (investimentos YouTube)

### Scripts Principais
1. `generate_analises_por_plataforma.py` - Análise CSV por plataforma
2. `generate_htmls_por_plataforma.py` - Conversão para HTML
3. `generate_analise_anuncios_FINAL.py` - Análise de vendas
4. `generate_analise_criativos_FINAL.py` - Análise de criativos
5. `generate_analise_meta_ads_com_investimentos.py` - Facebook + ROAS

---

## ✅ Validações Realizadas

### Integridade de Dados
- [x] Total de vendas: 568 (388 Hotmart + 180 TMB Vigente) ✓
- [x] Vendas rastreadas: 391 (68,8%) ✓
- [x] Leads CRM: 86.025 ✓
- [x] Leads rastreados: 83.357 (96,9%) ✓
- [x] Investimento Facebook: R$ 164.733,52 ✓
- [x] Investimento YouTube: R$ 187.230,85 ✓

### Consistência Cross-Platform
- [x] AD093: R$ 13.451 no YouTube (confirmado) ✓
- [x] AD054: R$ 29.730 no Facebook + R$ 14.530 no YouTube = R$ 44.260 total ✓
- [x] AD092: R$ 10.765 no Facebook + R$ 55.324 no YouTube = R$ 66.089 total ✓

### Cálculos de ROAS
- [x] Facebook: R$ 230.272 / R$ 164.733 = 1,40x ✓
- [x] YouTube: R$ 232.696 / R$ 187.230 = 1,24x ✓
- [x] Consolidado: R$ 462.968 / R$ 351.964 = 1,32x ✓

---

## 👤 Informações de Contato

**Data da Atualização:** 12 de Maio de 2026  
**Campanha:** PBB-ABR-26 (Banco do Brasil - Captação)  
**Período de Análise:** Abril 2026  
**Status:** ✅ Análises concluídas e validadas

---

**Fim do Relatório de Atualização**
