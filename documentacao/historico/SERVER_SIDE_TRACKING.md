# Server-Side Tracking — Plano e Implementação

**Última atualização:** Junho 2026  
**Status:** Planejado — nenhuma das abordagens implementada em produção  
**Objetivo:** Resolver subcontagem de leads e vendas causada por falhas de pixel client-side

---

## O Problema

Os pixels client-side (Google Ads, Meta) falham quando o lead é capturado via formulário + redirect, sem recarregamento da página. Resultado prático:

- **Google Ads** via pixel: vê ~5 conversões quando o CRM registra 15.784 leads
- **Meta** via pixel: sem rastreamento de lead via leads API (apenas thruplay)
- **Causa raiz:** Safari ITP, ad blockers, bounces antes do evento disparar e redirecionamentos que interrompem o script

A solução em ambas as abordagens é enviar o evento de conversão diretamente do servidor — sem depender do navegador.

---

## Abordagem A — Plugin WordPress (Rápida, Por Formulário)

**Ideal para:** resolver imediatamente o problema de leads via formulário nas LPs WordPress.  
**Complexidade:** Baixa — plugin PHP + credenciais no `wp-config.php`.  
**Data do plano:** Janeiro 2026

### Como funciona

```
Lead preenche formulário (WordPress LP)
    ↓
Plugin PHP intercepta o submit via AJAX
    ↓
Servidor WordPress chama diretamente:
    ├── Google Ads Conversions API
    └── Meta Conversions API (CAPI)
    ↓
Active Campaign registra o lead com UTMs
```

### Credenciais necessárias

```php
// wp-config.php
define('GOOGLE_ADS_CONVERSION_ID', '...');
define('GOOGLE_ADS_CONVERSION_LABEL', '...');
define('GOOGLE_ADS_CUSTOMER_ID', '...');
define('META_PIXEL_ID', '...');
define('META_ACCESS_TOKEN', '...');
define('META_EVENT_ID', 'Lead');
```

### Estrutura do plugin

```
/wp-content/plugins/conversions-tracker/
├── conversions-tracker.php         ← Plugin principal + handler AJAX
├── includes/
│   ├── class-google-conversions.php  ← Chama Google Ads Conversions API
│   ├── class-meta-conversions.php    ← Chama Meta CAPI
│   └── class-tracking-logger.php    ← Log de eventos em arquivo diário
└── js/form-tracker.js              ← Captura submit de formulários + extrai UTMs
```

### Dados enviados

Ambas as APIs recebem o e-mail com hash SHA-256, telefone normalizado E.164, UTMs da URL (`utm_campaign`, `utm_source`, `utm_medium`, `utm_content`) e timestamp. Nenhum dado bruto é enviado — apenas hashes.

### Validação

- Google Ads: verificar Conversion Action em `ads.google.com/aw/conversions` → status "Active"
- Meta: Events Debugger em `business.facebook.com/events_manager` → eventos "Lead" chegando em real-time
- Logs locais: `/wp-content/conversions-tracker-logs/tracking-YYYY-MM-DD.log`

---

## Abordagem B — GTM Server-Side Container (Completa, Multi-Domínio)

**Ideal para:** rastrear TODOS os eventos de todos os domínios Brabo, não apenas formulários.  
**Complexidade:** Alta — infra Docker + Traefik + SSL + 6 containers.  
**Data do plano:** Maio 2026

### Arquitetura

```
Internet (HTTPS)
    ↓
[Traefik - Reverse Proxy] (Portas 80/443 + SSL automático Let's Encrypt)
    ↓
    ├── GTM #1: lp.braboeditora.com.br      (Porta 9000 — TESTE)
    ├── GTM #2: braboeditora.com.br         (Porta 9001)
    ├── GTM #3: braboconcursos.com.br       (Porta 9002)
    ├── GTM #4: lp.braboconcursos.com.br    (Porta 9003)
    ├── GTM #5: mateusandrade.com.br        (Porta 9004)
    └── GTM #6: lp.mateusandrade.com.br     (Porta 9005)
```

### Infra disponível (servidor existente)

| Recurso | Capacidade |
|---------|-----------|
| RAM | 15 GB (9.3 GB livre) |
| CPU | 4 cores |
| Disco | 193 GB (153 GB livre) |
| Serviços já rodando | Docker v28.3.3, Traefik, n8n, Flowise, PostgreSQL, Redis |

### Recursos por container GTM

```yaml
limits:
  cpus: '1.0'
  memory: '2G'
reservations:
  cpus: '0.5'
  memory: '1G'
```

### Fases de rollout

| Fase | Domínio | Duração estimada |
|------|---------|-----------------|
| 1 — Teste | lp.braboeditora.com.br | 2-3 dias |
| 2 — Produção | braboeditora + braboconcursos + lp.braboconcursos | +2-3 dias |
| 3 — Expansão | mateusandrade + lp.mateusandrade | +1-2 dias |

### Pré-requisitos antes de iniciar

- [ ] DNS configurado e propagado para todos os 6 domínios
- [ ] GTM web container configurado para apontar ao server container
- [ ] Variáveis de ambiente (tokens Google/Meta) preparadas
- [ ] Volumes persistentes para logs criados

---

## Recomendação

**Para implementação imediata:** Abordagem A (plugin WordPress). Resolve o problema mais urgente (leads de formulário) em 1-2 dias, sem dependência de infra.

**Para solução definitiva:** Abordagem B (GTM server-side). Cobre todos os eventos, todos os domínios, com a stack padrão da indústria. Requer planejamento de infra mas é escalável para 300k+ leads/dia.

As abordagens não se excluem — é possível implementar A agora e migrar para B quando a infra estiver pronta.

---

## Referências

- Google Ads Conversions API: https://developers.google.com/google-ads/api/docs/conversions/conversion-uploads
- Meta Conversions API: https://developers.facebook.com/docs/conversions-api/
- GTM Server-Side: https://developers.google.com/tag-platform/tag-manager/server-side
