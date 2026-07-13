# Plano: Thumbnails e Reprodução de Vídeo via Meta API

**Status:** Aguardando implementação  
**Data:** 2026-06-25  
**Contexto:** Substituir o Google Drive como fonte de thumbnails de criativos Meta pelo dado direto da Marketing API, eliminando a dependência de upload manual de arquivos.

---

## Problema atual

O sistema atual busca thumbnails de criativos através do Google Drive:

1. Alguém salva o arquivo do criativo no Drive com nome `AD054 - ...`
2. O frontend chama a Drive API a cada request (cache 5 min)
3. O backend faz um redirect 302 para `thumbnailLink` do Drive (URL curta que expira)
4. Para o vídeo rodar, o popup usa `https://drive.google.com/file/d/{id}/preview`

**Problemas:** processo manual, URLs expiram, redirect por request, não escala.

---

## Solução proposta

### Fonte de dados

A Meta Marketing API fornece por anúncio:

| Campo | Endpoint | Expira? | Uso |
|---|---|---|---|
| `creative.thumbnail_url` | `/{ad_id}?fields=creative{thumbnail_url}` | Sim (~24-48h) | Preview estático |
| `creative.image_url` | `/{ad_id}?fields=creative{image_url}` | Sim (~24-48h) | Imagem (ads sem vídeo) |
| `creative.video_id` | `/{ad_id}?fields=creative{video_id}` | **Não** | ID permanente do vídeo |

A `thumbnail_url` expira, mas o ETL roda de hora em hora — na prática ela é sempre válida no banco (máx 1h de defasagem).

Para **rodar o vídeo**: o `video_id` é permanente. No momento do clique, o backend faz uma chamada on-demand a `/{video_id}?fields=source` e devolve a URL do MP4. Nunca fica desatualizado no banco.

### Arquitetura

```
ETL (por ad_id único, roda a cada hora):
  → fetch_creatives(ad_ids) via Meta API
  → upsert em meta_ads_creatives(ad_id, thumbnail_url, video_id, image_url, fetched_at)

Frontend — thumbnail:
  → lê meta_ads_creatives.thumbnail_url direto do banco
  → sem redirect, sem Drive

Frontend — reprodução de vídeo:
  → usuário clica no popup
  → chama GET /api/meta-video/{ad_id}
  → backend: SELECT video_id FROM meta_ads_creatives WHERE ad_id = ?
  → backend: GET /{video_id}?fields=source (Meta API, on-demand)
  → retorna JSON { url: "https://..." }
  → popup abre <video src="..."> e reproduz
```

---

## Etapas de implementação

### 1. Schema — nova tabela no Supabase (Analytics DB)

Rodar no SQL Editor:

```sql
CREATE TABLE IF NOT EXISTS meta_ads_creatives (
    ad_id           TEXT        PRIMARY KEY,
    thumbnail_url   TEXT,
    image_url       TEXT,
    video_id        TEXT,
    fetched_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index para lookup rápido por video_id (usado no endpoint de reprodução)
CREATE INDEX IF NOT EXISTS idx_mac_video_id ON meta_ads_creatives (video_id);
```

### 2. ETL — `etl/etl_meta_ads.py`

Adicionar função `fetch_creatives(ad_ids)` que:

- Recebe lista de `ad_id` únicos do período
- Faz batch requests à Meta API (máx 50 por request, usar `?ids=id1,id2,...`)
- Endpoint: `https://graph.facebook.com/v22.0/?ids={ids}&fields=creative{thumbnail_url,image_url,video_id}&access_token={token}`
- Faz upsert em `meta_ads_creatives`

Chamar ao final do `run_api_mode()`, passando os `ad_id` únicos do DataFrame inserido.

```python
def fetch_creatives(ad_ids: list[str], token: str) -> list[dict]:
    """Busca dados de criativo (thumbnail, video_id) para uma lista de ad_ids."""
    results = []
    batch_size = 50
    for i in range(0, len(ad_ids), batch_size):
        batch = ad_ids[i:i + batch_size]
        ids_param = ",".join(batch)
        url = f"https://graph.facebook.com/{API_VERSION}/"
        params = {
            "ids": ids_param,
            "fields": "creative{thumbnail_url,image_url,video_id}",
            "access_token": token,
        }
        r = http_get(url, params=params)
        data = r.json()
        for ad_id, ad_data in data.items():
            creative = ad_data.get("creative", {})
            results.append({
                "ad_id":         ad_id,
                "thumbnail_url": creative.get("thumbnail_url"),
                "image_url":     creative.get("image_url"),
                "video_id":      creative.get("video_id"),
            })
    return results


def upsert_creatives(rows: list[dict], engine) -> None:
    if not rows:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO meta_ads_creatives (ad_id, thumbnail_url, image_url, video_id, fetched_at)
            VALUES (:ad_id, :thumbnail_url, :image_url, :video_id, NOW())
            ON CONFLICT (ad_id) DO UPDATE SET
                thumbnail_url = EXCLUDED.thumbnail_url,
                image_url     = EXCLUDED.image_url,
                video_id      = EXCLUDED.video_id,
                fetched_at    = NOW()
        """), rows)
    logger.info("upsert_creatives: %d registros atualizados", len(rows))
```

### 3. Frontend — leitura do banco (`frontend/database_reader.py`)

Adicionar função `get_meta_creatives(launch_code)`:

```python
def get_meta_creatives(launch_code: str) -> dict[str, dict]:
    """Retorna {ad_id: {thumbnail_url, image_url, video_id}} para um lançamento."""
    engine = _get_engine()
    df = pd.read_sql(
        text("""
            SELECT DISTINCT ON (mac.ad_id)
                mac.ad_id, mac.thumbnail_url, mac.image_url, mac.video_id
            FROM meta_ads_creatives mac
            JOIN meta_ads_daily mad ON mad.ad_id = mac.ad_id
            WHERE mad.lancamento_codigo = :code
        """),
        engine,
        params={"code": launch_code}
    )
    if df.empty:
        return {}
    return df.set_index("ad_id")[["thumbnail_url", "image_url", "video_id"]].to_dict("index")
```

### 4. Frontend — endpoint de reprodução de vídeo (`frontend/app.py` ou rota dedicada)

```python
@app.get("/api/meta-video/{ad_id}")
async def meta_video_url(ad_id: str, request: Request):
    """Retorna a URL do MP4 do vídeo Meta on-demand (não armazenado pois expira)."""
    # Busca video_id no banco
    engine = _get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT video_id FROM meta_ads_creatives WHERE ad_id = :ad_id"),
            {"ad_id": ad_id}
        ).fetchone()
    if not row or not row[0]:
        return JSONResponse({"error": "video_id não encontrado"}, status_code=404)

    video_id = row[0]
    token = os.environ["META_ACCESS_TOKEN"]
    r = http_get(
        f"https://graph.facebook.com/{API_VERSION}/{video_id}",
        params={"fields": "source", "access_token": token}
    )
    data = r.json()
    source_url = data.get("source")
    if not source_url:
        return JSONResponse({"error": "URL do vídeo não disponível"}, status_code=404)

    return JSONResponse({"url": source_url})
```

### 5. Frontend — popup do criativo (template HTML)

Onde hoje usa `drive_thumbnails[ad_code].thumb`, substituir por `creatives[ad_id].thumbnail_url` (ou `image_url` como fallback).

Para reprodução:

```javascript
// Ao clicar no criativo
async function playMetaVideo(adId) {
    const res = await fetch(`/api/meta-video/${adId}`);
    const data = await res.json();
    if (data.url) {
        document.getElementById('video-player').src = data.url;
        document.getElementById('video-modal').style.display = 'block';
    }
}
```

---

## Transição / Fallback

Durante a migração, manter o Drive como fallback:

```
Se creatives[ad_code] existir → usa Meta API
Senão → tenta drive_thumbnails[ad_code] (Drive, legado)
Senão → mostra placeholder
```

Após validar que todos os lançamentos ativos têm criativos no banco, remover o Drive.

---

## O que NÃO muda

- Google Ads / YouTube: `video_id` já está no banco (`google_ads_daily.video_id`). Thumbnail via `https://img.youtube.com/vi/{VIDEO_ID}/hqdefault.jpg` — implementar separado, sem ETL adicional.
- Drive: continua montado via `/analises` para reports v1 legados.

---

## Dependências

- Token Meta com permissão `ads_read` (já disponível no `.env`)
- Rodar o SQL do schema antes da primeira execução do ETL
- Sem nova dependência de biblioteca (usa `http_get` já presente)
