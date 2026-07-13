#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOCUMENTAÇÃO DE ANÁLISE - PBB-ABR-26
====================================

Este arquivo documenta como executar as análises de dados de vendas e leads
para o projeto Banco do Brasil - Abril 2026.

ATUALIZADO: 12/05/2026 14:53
"""

# =============================================================================
# 1. AMBIENTE & PREPARAÇÃO
# =============================================================================

"""
Ativar ambiente virtual:
  cd C:\Users\trafe\OneDrive\Desktop\workspace-mmm
  .\.venv\Scripts\Activate.ps1

Verificar Python:
  python --version
  pip list | grep pandas
"""

# =============================================================================
# 2. ESTRUTURA DE DADOS
# =============================================================================

"""
ARQUIVOS NECESSÁRIOS:

1. CRM/LEADS (Active Campaign)
   - Arquivo: analises/[PBB-ABR-26]/Active Campaign/Banco do Brasil- 24-04-26.csv
   - Linhas: 81.261 leads
   - Colunas: Email, utm_source, utm_medium, utm_campaign, utm_content, etc
   - Encoding: UTF-8
   - Separador: VÍRGULA (,)

2. VENDAS - HOTMART
   - Arquivo: analises/[PBB-ABR-26]/Vendas/hotmart-pbb-abr-26.csv
   - Linhas: 388 vendas
   - Colunas importantes:
     * Email do(a) Comprador(a): email para matching
     * Faturamento bruto (sem impostos): valor de receita (R$ 360.351,19 total)
   - Encoding: UTF-8
   - Separador: PONTO-VÍRGULA (;)
   - Valores: Em REAIS (não em centavos)
   - Formato Número: PONTO como decimal (249.90)

3. VENDAS - TMB
   - Arquivo: analises/[PBB-ABR-26]/Vendas/tmb-pbb-abr-26.csv
   - Linhas: 183 vendas
   - Colunas importantes:
     * E-mail do Cliente: email para matching
     * Ticket do pedido: valor de receita (R$ 297.484,90 total)
   - Encoding: UTF-8
   - Separador: PONTO-VÍRGULA (;)
   - Valores: Em REAIS (não em centavos)
   - Formato Número: PONTO como decimal (474.90)

4. DADOS DE ANÚNCIOS (EXCEL)
   - Arquivo: Anúncios [PBB-ABR-26] (7).xlsx
   - Sheets: EXTRACAO-BM (Facebook), EXTRACAO-GA (Google Ads)
   - Dados: Spend, Leads, Conversions por criativo
"""

# =============================================================================
# 3. SCRIPTS PRINCIPAIS & COMO EXECUTAR
# =============================================================================

"""
🚀 SCRIPT 1: Gerar Todos os Relatórios HTML
────────────────────────────────────────────
Arquivo: generate_all_reports_pbb_abr.py
Função: Cria 8 relatórios HTML com análises completas
Output: Múltiplos HTML em analises/[PBB-ABR-26]/

Execução:
  .\.venv\Scripts\python.exe generate_all_reports_pbb_abr.py

Outputs Gerados:
  ✓ INDEX_[PBB-ABR-26].html - Página principal com links
  ✓ ANALISE_META_ADS_[PBB-ABR-26].html - Performance Meta/Facebook
  ✓ ANALISE_GOOGLE_ADS_[PBB-ABR-26].html - Performance Google Ads
  ✓ ANALISE_LEADS_CONFRONTO_[PBB-ABR-26].html - Comparação Excel vs CRM
  ✓ ANALISE_ANUNCIOS_[PBB-ABR-26].html - Consolidação anúncios
  ✓ ANALISE_META_AUDIENCES_[PBB-ABR-26].html - Públicos Meta
  ✓ ANALISE_GOOGLE_AUDIENCES_[PBB-ABR-26].html - Públicos Google
  ✓ INSIGHTS_RECOMENDACOES_[PBB-ABR-26].html - Conclusões e sugestões

Tempo: ~2-3 minutos
Status: ✅ WORKING


🚀 SCRIPT 2: Análise de Vendas por Criativo
────────────────────────────────────────────
Arquivo: analise_vendas_por_criativo_detalhada.py
Função: Associa 571 vendas com 39 criativos via UTM + Email matching
Output: VENDAS_POR_CRIATIVO_[PBB-ABR-26].html + .csv

Execução:
  .\.venv\Scripts\python.exe analise_vendas_por_criativo_detalhada.py

Resultado Esperado:
  - Total: 571 vendas = R$ 657.836,09
  - Rastreadas (com UTM): 399 vendas = R$ 472.917,14
  - Sem UTM: 172 vendas = R$ 184.918,95
  - Ticket Médio: R$ 1.152,08
  - Taxa de Rastreamento: 69,9%
  - Top Criativo: AD054 com 40 vendas

Top 3 Criativos por Vendas:
  1. AD054 - Banco do Brasil + IA: 40 vendas
  2. ad092 - Dois personagens: 36 vendas
  3. ad050: 29 vendas

Status: ✅ WORKING (valores corrigidos 12/05)


🚀 SCRIPT 3: Comparação Excel vs CRM
──────────────────────────────────────
Arquivo: analise_comparativa_excel_crm.py
Função: Reconciliação de leads (Excel como referencial vs CRM real)
Output: Relatório na console com análise de gaps

Execução:
  .\.venv\Scripts\python.exe analise_comparativa_excel_crm.py

Mostra:
  - Leads no Excel vs CRM
  - Investimento por plataforma (Facebook vs Google)
  - GAP identificado
  - Recomendações de investigação

Resultado Esperado:
  - Excel: 87.781 leads (59.372 FB + 28.409 GA)
  - CRM: 81.261 leads
  - GAP: -6.520 leads (-7.4%)
  - ROAS: ~2.15x

Status: ✅ WORKING


🚀 SCRIPT 4: Validação vs Dados Oficiais
─────────────────────────────────────────
Arquivo: comparacao_final.py
Função: Compara CSVs locais com dados do dashboard oficial
Output: Identifica discrepâncias de receita e quantidade

Execução:
  .\.venv\Scripts\python.exe comparacao_final.py

Resultado Esperado:
  Oficial: R$ 864.482,62 (549 vendas)
  CSVs: R$ 657.836,09 (571 vendas)
  Diferença: -R$ 206.646,53 (-23,9%)
  
  Diagnóstico: Há 22 vendas a MAIS nos CSVs, mas faltam R$ 206K de receita
  Possível Causa: Vendas em outras plataformas ou período incompleto

Status: ✅ WORKING (novo, 12/05)
"""

# =============================================================================
# 4. FORMATO CORRETO DE DADOS - ⚠️ CRÍTICO
# =============================================================================

"""
❌ ERROS COMUNS:

1. DIVIDIR VALORES POR 100
   ❌ df['valor'] = df['valor'] / 100
   ✅ df['valor'] = df['valor']  # Já estão em reais!
   
2. TRANSFORMAR PONTO EM VÍRGULA E VICE-VERSA
   ❌ valor.replace('.', '').replace(',', '.')
   ✅ Decimal(valor_str)  # Ponto já é correto!

3. NÃO USAR quoting=1 AO LER CSV
   ❌ df = pd.read_csv(file, sep=';')
   ✅ df = pd.read_csv(file, sep=';', quoting=1, low_memory=False)
   
4. EMAIL MATCHING SEM NORMALIZAÇÃO
   ❌ df['email'].merge(df_vendas['email'])
   ✅ df['email'].str.strip().str.lower().merge(...)

────────────────────────────────────────────────────────────────────────────

✅ FORMATO CORRETO:

HOTMART:
  Arquivo: hotmart-pbb-abr-26.csv
  Separador: Ponto-vírgula (;)
  Valores: Decimal.PONTO (249.90)
  Coluna Valor: "Faturamento bruto (sem impostos)"
  Tratamento: 
    valor = Decimal(row['Faturamento bruto (sem impostos)'])
  Total: R$ 360.351,19

TMB:
  Arquivo: tmb-pbb-abr-26.csv
  Separador: Ponto-vírgula (;)
  Valores: Decimal.PONTO (474.90)
  Coluna Valor: "Ticket do pedido"
  Tratamento:
    valor = Decimal(row['Ticket do pedido'])
  Total: R$ 297.484,90

CRM/ACTIVE CAMPAIGN:
  Arquivo: Banco do Brasil- 24-04-26.csv
  Separador: Vírgula (,)
  Colunas Email: [varias possibilidades]
  Tratamento CSV:
    pd.read_csv(file, sep=',', encoding='utf-8', quoting=1, low_memory=False)
  Total Leads: 81.261
"""

# =============================================================================
# 5. FLUXO COMPLETO DE ANÁLISE
# =============================================================================

"""
PASSO A PASSO PARA ANÁLISE COMPLETA:

1️⃣ PREPARAÇÃO
   [ ] Verificar se todos os 4 arquivos existem
   [ ] Ativar ambiente virtual (.venv)
   [ ] Abrir terminal no diretório raiz do projeto

2️⃣ GERAR RELATÓRIOS
   [ ] Executar: generate_all_reports_pbb_abr.py
   [ ] Verificar: 8 HTMLs criados em analises/[PBB-ABR-26]/
   [ ] Abrir: INDEX_[PBB-ABR-26].html no navegador

3️⃣ ANÁLISE DE VENDAS POR CRIATIVO
   [ ] Executar: analise_vendas_por_criativo_detalhada.py
   [ ] Verificar: 571 vendas, R$ 657.836,09
   [ ] Output: VENDAS_POR_CRIATIVO_[PBB-ABR-26].html e .csv

4️⃣ RECONCILIAÇÃO
   [ ] Executar: analise_comparativa_excel_crm.py
   [ ] Analisar: GAP de 7.4% em leads (Excel vs CRM)
   [ ] Documentar: Achados para investigação

5️⃣ VALIDAÇÃO (NOVO)
   [ ] Executar: comparacao_final.py
   [ ] Revisar: Discrepância vs dados oficiais
   [ ] Investigar: Se faltam R$ 206K, procurar causas

6️⃣ DOCUMENTAÇÃO
   [ ] Atualizar relatório de findings
   [ ] Registrar discrepâncias e causas possíveis
   [ ] Criar plano de ação para gaps

⏱️ Tempo Total: ~15 minutos
"""

# =============================================================================
# 6. MÉTRICAS PRINCIPAIS & VALIDAÇÃO
# =============================================================================

"""
MÉTRICAS ESPERADAS (12/05/2026):

✅ VENDAS:
   Hotmart: 388 vendas = R$ 360.351,19
   TMB: 183 vendas = R$ 297.484,90
   TOTAL: 571 vendas = R$ 657.836,09
   Ticket Médio: R$ 1.152,08

✅ LEADS CRM:
   Total: 81.261 leads
   Taxa de Conversão: 0.70% (571 vendas / 81.261 leads)

✅ CRIATIVOS:
   Total: 39 criativos únicos
   Rastreados: 399 vendas (69,9%)
   Sem UTM: 172 vendas (30,1%)
   Top: AD054 com 40 vendas

⚠️ DISCREPÂNCIAS CONHECIDAS:
   vs Oficial: -R$ 206.646,53 (-23,9% em receita)
   Vendas+: +22 vendas (+4%)
   
   Causa: Investigar se há:
   - Vendas em outras plataformas
   - Cancelamentos/reembolsos
   - Período incompleto
"""

# =============================================================================
# 7. TROUBLESHOOTING & FAQ
# =============================================================================

"""
❓ P: Erro "out of memory" ao ler CSV
✓ R: Adicionar quoting=1, low_memory=False ao pd.read_csv()

❓ P: Valores saem 100x maiores
✓ R: Não dividir por 100! Valores já estão em reais.

❓ P: Email matching não funciona
✓ R: Normalizar com .strip().lower() em AMBOS os dataframes

❓ P: Qual coluna de valor usar? (Bruto vs Líquido)
✓ R: Hotmart usa "Faturamento bruto (sem impostos)" - é mais próximo do oficial

❓ P: Por que tem +22 vendas mas -23,9% em receita?
✓ R: Possível causa: Vendas em outras plataformas ou período incompleto

❓ P: Como rodar apenas UM script sem executar todos?
✓ R: Executar diretamente: .\.venv\Scripts\python.exe SCRIPT.py

❓ P: Os scripts podem rodar em paralelo?
✓ R: Não recomendado - executar sequencialmente (consomem muita memória)
"""

# =============================================================================
# 8. PRÓXIMAS AÇÕES & ROADMAP
# =============================================================================

"""
🎯 AÇÕES IMEDIATAS (12/05/2026):
[ ] Investigar origem de R$ 206.646,53 faltando
[ ] Validar data/período dos arquivos
[ ] Procurar vendas em outras plataformas
[ ] Auditar cancelamentos/reembolsos

🎯 MELHORIAS FUTURAS:
[ ] Integração com API oficial para sync de dados
[ ] Dashboard real-time de vendas
[ ] Alertas automáticos de discrepâncias
[ ] Exportação de dados em mais formatos

🎯 DOCUMENTAÇÃO:
[ ] Criar guia de reprodução da análise
[ ] Documentar todos os erros e soluções
[ ] Manutenção de metadata de arquivos
"""

# =============================================================================
# FIM DA DOCUMENTAÇÃO
# =============================================================================
