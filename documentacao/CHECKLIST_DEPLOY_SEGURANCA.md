# Checklist de Segurança para Deploy — Brabo Analytics

Execute esta lista antes de subir ao servidor de produção.

---

## 1. Variáveis de Ambiente obrigatórias (.env no servidor)

```env
# ── Banco de dados ─────────────────────────────────────────────────────────────
SUPABASE_DB_URL=postgresql://...        # Connection string completa com senha
SUPABASE_USERS_URL=postgresql://...     # Idem para o banco operacional

# ── Sessão ─────────────────────────────────────────────────────────────────────
SECRET_KEY=<64 caracteres aleatórios>   # Gerar com: python -c "import secrets; print(secrets.token_urlsafe(48))"
SESSION_MAX_AGE=86400                   # 1 dia em segundos (ajustar conforme política)
COOKIE_SECURE=true                      # OBRIGATÓRIO quando HTTPS estiver ativo

# ── Credenciais legado (fallback quando DB cai) ────────────────────────────────
BRABO_USER=<email-do-admin>             # Não usar "brabo" em produção
BRABO_PASS=<senha-forte-20+-chars>      # Não usar "pbb2026" em produção

# ── HSTS (ativar após confirmar que HTTPS funciona) ────────────────────────────
HSTS_MAX_AGE=31536000                   # 1 ano — só ativar depois de confirmar HTTPS ok

# ── APIs externas ──────────────────────────────────────────────────────────────
META_ACCESS_TOKEN=...
META_AD_ACCOUNT_ID=...
GOOGLE_ADS_DEVELOPER_TOKEN=...
GOOGLE_ADS_CLIENT_ID=...
GOOGLE_ADS_CLIENT_SECRET=...
GOOGLE_ADS_REFRESH_TOKEN=...
GOOGLE_ADS_CUSTOMER_ID=...
GOOGLE_ADS_LOGIN_CUSTOMER_ID=...
AC_API_URL=...
AC_API_KEY=...
TYPEFORM_TOKEN=...
TYPEFORM_FORM_ID=...

# ── Alertas ETL ────────────────────────────────────────────────────────────────
ERROR_WEBHOOK_URL=<discord-ou-slack-webhook>
```

---

## 2. Permissões de Arquivo no Servidor

```bash
# .env — só o processo da aplicação pode ler
chmod 600 .env

# Chave da service account Google Drive
chmod 600 json/uplifted-kit-499213-d8-6c09276f2753.json
chmod 700 json/

# Logs — escrita pelo app, leitura restrita
chmod 750 logs/
```

---

## 3. Gerar SECRET_KEY forte

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Exemplo de saída: 3x9Kp2mNqRvTwYjL8cZs...  (64 chars)
```

Nunca reutilizar a mesma `SECRET_KEY` em múltiplos ambientes. Se vazar, todos os cookies de sessão ficam comprometidos.

---

## 4. HTTPS obrigatório

O deploy **deve** ficar atrás de um proxy reverso com HTTPS (nginx + Let's Encrypt ou Caddy).

Depois de confirmar HTTPS funcionando:
1. Setar `COOKIE_SECURE=true` no `.env`
2. Setar `HSTS_MAX_AGE=31536000` no `.env`
3. Reiniciar a aplicação

**Não ative HSTS antes de confirmar que HTTPS funciona** — se ativar com HTTP, o browser bloqueia o site e não tem como reverter facilmente.

Exemplo mínimo de configuração nginx:

```nginx
server {
    listen 443 ssl;
    server_name seu-dominio.com;

    ssl_certificate     /etc/letsencrypt/live/seu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seu-dominio.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name seu-dominio.com;
    return 301 https://$host$request_uri;
}
```

---

## 5. Rodar como usuário sem privilégios

```bash
# Criar usuário dedicado sem shell e sem sudo
useradd -r -s /bin/false brabo-app

# Dar ownership apenas dos arquivos necessários
chown -R brabo-app:brabo-app /opt/brabo-analytics

# Rodar uvicorn como esse usuário (via systemd ou supervisor)
```

---

## 6. Systemd service (rodar o app automaticamente)

```ini
# /etc/systemd/system/brabo-app.service
[Unit]
Description=Brabo Analytics Dashboard
After=network.target

[Service]
User=brabo-app
WorkingDirectory=/opt/brabo-analytics
EnvironmentFile=/opt/brabo-analytics/.env
ExecStart=/opt/brabo-analytics/.venv/bin/uvicorn frontend.app:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable brabo-app
systemctl start brabo-app
```

```ini
# /etc/systemd/system/brabo-scheduler.service
[Unit]
Description=Brabo Analytics ETL Scheduler
After=network.target

[Service]
User=brabo-app
WorkingDirectory=/opt/brabo-analytics
EnvironmentFile=/opt/brabo-analytics/.env
ExecStart=/opt/brabo-analytics/.venv/bin/python etl/scheduler.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

---

## 7. Verificação pós-deploy

```bash
# Headers de segurança presentes
curl -I https://seu-dominio.com/login | grep -E "X-Frame|X-Content|X-XSS|Referrer"

# /health retorna apenas {"status":"ok"} para não autenticados
curl https://seu-dominio.com/health
# Esperado: {"status":"ok"}  — sem detalhes de DB

# /health com admin retorna detalhes
# (logar como admin e usar o cookie)

# HTTPS redireciona HTTP
curl -I http://seu-dominio.com/
# Esperado: 301 → https://
```

---

## 8. O que NÃO fazer

| ❌ Evitar | ✅ Correto |
|---|---|
| Commitar `.env` no git | `.gitignore` já cobre — verificar antes de push |
| Commitar `json/` no git | `.gitignore` já cobre |
| Usar `SECRET_KEY=brabo-dev-*` em produção | App loga warning — troca obrigatória |
| Usar `BRABO_PASS=pbb2026` em produção | Troca obrigatória |
| Rodar como root | Usar usuário `brabo-app` sem privilégios |
| Expor porta 8000 diretamente | Sempre atrás de nginx/Caddy |
| Ativar HSTS antes de confirmar HTTPS | Pode bloquear acesso permanentemente |

---

## 9. O que já está protegido no código

| Proteção | Status |
|---|---|
| SQL injection | ✅ Todos os inputs em parâmetros bindados |
| XSS | ✅ Jinja2 escapa por padrão; único `\| safe` é de arquivo local |
| CSRF | ✅ `samesite=lax` no cookie de sessão |
| Clickjacking | ✅ `X-Frame-Options: DENY` (adicionado na sessão) |
| MIME sniffing | ✅ `X-Content-Type-Options: nosniff` (adicionado) |
| Brute force no login | ✅ 10 tentativas / 5 min por IP |
| Sessão forjada | ✅ HMAC-SHA256 com `compare_digest` |
| Senhas | ✅ bcrypt |
| Writes acidentais no DB | ✅ Guard SQLAlchemy nas tabelas read-only |
| Command injection | ✅ `subprocess` sem `shell=True` |
| Credenciais hardcoded | ✅ Tudo via `.env`; warning se SECRET_KEY fraca |
