-- Migration 006: guarda os bytes das thumbnails do Meta em ad_creatives.
-- As URLs do CDN do Facebook (thumbnail_url/image_url) são assinadas e expiram
-- em poucas semanas — mesma lição do Drive (creative_thumbnails): persistir a
-- imagem no banco no momento do ETL, quando a URL ainda está fresca, e servir
-- de lá para sempre.
ALTER TABLE ad_creatives
    ADD COLUMN IF NOT EXISTS thumb_data BYTEA,
    ADD COLUMN IF NOT EXISTS thumb_content_type TEXT,
    ADD COLUMN IF NOT EXISTS image_data BYTEA,
    ADD COLUMN IF NOT EXISTS image_content_type TEXT;
