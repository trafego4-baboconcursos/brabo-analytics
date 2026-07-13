import os
import re
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine

load_dotenv()

def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode('ascii'))

def parse_br_date(date_str):
    return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()

def extract_launches_from_html() -> list[dict]:
    html_path = Path("c:/Users/trafe/OneDrive/Desktop/workspace-mmm/analises/[PBB-ABR-26]/SISTEMA_CALENDARIO_2026.html")
    if not html_path.exists():
        safe_print("Erro: Arquivo do calendario HTML nao encontrado em " + str(html_path))
        sys.exit(1)
        
    content = html_path.read_text(encoding="utf-8")
    
    # Regex para capturar codigo do lançamento, etapa, data de inicio e data de fim
    pattern = re.compile(
        r'<tr[^>]*data-launch=["\']([^"\']+)["\'][^>]*>.*?<span[^>]*class=["\']stage [^"\']*["\'][^>]*>([^<]+)</span>.*?<td>(\d{2}/\d{2}/\d{4})</td>\s*<td>(\d{2}/\d{2}/\d{4})</td>',
        re.DOTALL
    )
    
    matches = pattern.findall(content)
    
    launches_stages = {}
    for launch_code, stage, start_date, end_date in matches:
        launch_code = launch_code.strip().upper()
        stage = stage.strip()
        launches_stages.setdefault(launch_code, []).append({
            "start": parse_br_date(start_date),
            "end": parse_br_date(end_date)
        })
        
    launches_list = []
    for code, stages in launches_stages.items():
        # Calcula inicio global (minima data de inicio das etapas)
        # e fim global (maxima data de fim das etapas)
        start_global = min(s["start"] for s in stages)
        end_global = max(s["end"] for s in stages)
        
        # Determina o projeto pelo prefixo do codigo
        if code.startswith("PI-"):
            projeto = "INSS"
        elif code.startswith("PES-"):
            projeto = "TJ"
        elif code.startswith("PBB-"):
            projeto = "BB"
        else:
            projeto = "Outro"
            
        launches_list.append({
            "codigo": code,
            "nome": code,
            "projeto": projeto,
            "data_inicio": start_global,
            "data_fim": end_global
        })
        
    return launches_list

def main():
    engine = get_engine()
    
    # 1. Extrai do HTML
    safe_print("Extraindo cronograma do calendario HTML...")
    launches = extract_launches_from_html()
    safe_print(f"Encontrados {len(launches)} lancamentos no HTML.")
    
    # 2. Insere na dim_lancamentos
    safe_print("Gravando dim_lancamentos no Supabase...")
    with engine.begin() as conn:
        for l in launches:
            q = text("""
                INSERT INTO dim_lancamentos (codigo, nome, projeto, data_inicio, data_fim, updated_at)
                VALUES (:codigo, :nome, :projeto, :data_inicio, :data_fim, NOW())
                ON CONFLICT (codigo) DO UPDATE
                SET nome = EXCLUDED.nome,
                    projeto = EXCLUDED.projeto,
                    data_inicio = EXCLUDED.data_inicio,
                    data_fim = EXCLUDED.data_fim,
                    updated_at = NOW()
            """)
            conn.execute(q, {
                "codigo": l["codigo"],
                "nome": l["nome"],
                "projeto": l["projeto"],
                "data_inicio": l["data_inicio"],
                "data_fim": l["data_fim"]
            })
            safe_print(f"  - Gravado: {l['codigo']} ({l['data_inicio']} ate {l['data_fim']})")
            
    # 3. Atualiza colunas operacionais retroativamente
    safe_print("Atualizando 'lancamento_codigo' retroativamente nas tabelas operacionais...")
    with engine.begin() as conn:
        # A. Meta Ads por campanha
        safe_print("  - Atualizando meta_ads_daily a partir do campaign_name...")
        conn.execute(text("UPDATE meta_ads_daily SET lancamento_codigo = NULL"))
        res = conn.execute(text("""
            UPDATE meta_ads_daily 
            SET lancamento_codigo = upper(substring(campaign_name from '((PBB|PES|PI|pbb|pes|pi)-[a-zA-Z]{3}-[0-9]{2})'))
            WHERE campaign_name IS NOT NULL;
        """))
        safe_print(f"    Meta Ads atualizados por campanha: {res.rowcount} linhas.")
        
        # B. Google Ads por campanha
        safe_print("  - Atualizando google_ads_daily a partir do campaign_name...")
        conn.execute(text("UPDATE google_ads_daily SET lancamento_codigo = NULL"))
        res = conn.execute(text("""
            UPDATE google_ads_daily 
            SET lancamento_codigo = upper(substring(campaign_name from '((PBB|PES|PI|pbb|pes|pi)-[a-zA-Z]{3}-[0-9]{2})'))
            WHERE campaign_name IS NOT NULL;
        """))
        safe_print(f"    Google Ads atualizados por campanha: {res.rowcount} linhas.")
        
        # C. Active Campaign (Leads) por utm_campaign
        safe_print("  - Atualizando leads a partir do utm_campaign...")
        conn.execute(text("UPDATE leads SET lancamento_codigo = NULL"))
        res = conn.execute(text("""
            UPDATE leads 
            SET lancamento_codigo = upper(substring(utm_campaign from '((PBB|PES|PI|pbb|pes|pi)-[a-zA-Z]{3}-[0-9]{2})'))
            WHERE utm_campaign IS NOT NULL;
        """))
        safe_print(f"    Leads atualizados por utm_campaign: {res.rowcount} linhas.")

        # D. Atribuicao complementar de Leads por data + ad_code
        safe_print("  - Atribuindo leads sem lancamento_codigo baseado no anuncio (ADXXX) e data...")
        res = conn.execute(text("""
            WITH lead_ads AS (
                SELECT 
                    l.id,
                    COALESCE(m.lancamento_codigo, g.lancamento_codigo) AS ad_launch
                FROM leads l
                LEFT JOIN meta_ads_daily m 
                  ON upper(regexp_replace(l.utm_content, '^(AD\\d+).*', '\\1')) = upper(regexp_replace(m.ad_name, '^(AD\\d+).*', '\\1'))
                  AND l.created_at::date = m.date
                LEFT JOIN google_ads_daily g 
                  ON upper(regexp_replace(l.utm_content, '^(AD\\d+).*', '\\1')) = upper(regexp_replace(g.ad_name, '^(AD\\d+).*', '\\1'))
                  AND l.created_at::date = g.date
                WHERE l.lancamento_codigo IS NULL 
                  AND l.utm_content IS NOT NULL AND l.utm_content <> ''
                  AND COALESCE(m.lancamento_codigo, g.lancamento_codigo) IS NOT NULL
            )
            UPDATE leads l
            SET lancamento_codigo = la.ad_launch
            FROM lead_ads la
            WHERE l.id = la.id;
        """))
        safe_print(f"    Leads complementados por data/anuncio: {res.rowcount} linhas.")
        
    safe_print("Migracao concluida com sucesso!")

if __name__ == "__main__":
    main()
