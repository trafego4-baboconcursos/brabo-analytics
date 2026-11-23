import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from check_retry_group_01 import query_google_ads

def main():
    cid = "6482320788"
    q = """
    SELECT
        asset.id,
        asset.name,
        asset.youtube_video_asset.youtube_video_id,
        asset.youtube_video_asset.youtube_video_title
    FROM asset
    WHERE asset.type = 'YOUTUBE_VIDEO'
    """
    res = query_google_ads(cid, q)
    print(f"Total de assets de vídeo encontrados: {len(res)}")
    for item in res:
        a = item['asset']
        yt = a.get('youtubeVideoAsset', {})
        t = (yt.get('youtubeVideoTitle') or '') + ' ' + (a.get('name') or '')
        if any(k in t.lower() for k in ['bv', 'mateus', 'ma0', 'tr', 'aquecimento', 'cleyton', 'ugc', 'inseguro', 'reclamando']):
            print(f"Asset ID: {a['id']} | YT ID: {yt.get('youtubeVideoId')} | Titulo: {yt.get('youtubeVideoTitle')}")

if __name__ == "__main__":
    main()
