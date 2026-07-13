import os
import sys
import re
import json
import unicodedata
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Adiciona o diretorio pai ao path para importar modulos
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from db import get_engine
from etl_active_campaign import load_from_csv as load_ac_csv
from etl_meta_ads import build_df_from_csv as load_meta_csv
from etl_google_ads import build_df_from_csv as load_google_csv
from migration_retroactive import main as run_migration

load_dotenv()

# Map launch folders to Google Ads periods
LAUNCH_PERIODS = {
    "[PI-JAN-26]": "2026-01",
    "[PES-JAN-26]": "2026-01",
    "[PBB-FEV-26]": "2026-02",
    "[PES-MAR-26]": "2026-03",
    "[PI-ABR-26]": "2026-04",
    "[PBB-ABR-26]": "2026-04",
    "[PES-MAI-26]": "2026-05",
}

def _detect_encoding(path: Path) -> str:
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with path.open(encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "latin-1"

def _detect_separator(path: Path, enc: str) -> str:
    with path.open(encoding=enc, errors="replace") as f:
        first_line = f.readline()
    if first_line.count(";") > first_line.count(","):
        return ";"
    return ","

def load_typeform_csv(filepath: Path, form_id: str) -> pd.DataFrame:
    enc = _detect_encoding(filepath)
    sep = _detect_separator(filepath, enc)
    df = pd.read_csv(filepath, sep=sep, encoding=enc, dtype=str, low_memory=False)
    
    # 1. Encontra e-mail
    email_col = None
    for col in df.columns:
        col_norm = col.lower().strip()
        if "digite o seu e-mail" in col_norm or "digite seu e-mail" in col_norm or "e-mail" in col_norm or "email" in col_norm:
            email_col = col
            break
    if not email_col:
        return pd.DataFrame()
        
    df["email"] = df[email_col].astype(str).str.strip().str.lower()
    df = df[df["email"].str.contains("@", na=False)].copy()
    
    # 2. Encontra submitted_at
    sub_col = None
    for col in df.columns:
        col_norm = col.lower().strip()
        if "submit date" in col_norm or "submitted at" in col_norm or "data de envio" in col_norm or "submit" in col_norm or "date" in col_norm:
            sub_col = col
            break
            
    if sub_col:
        df["submitted_at"] = pd.to_datetime(df[sub_col], errors="coerce")
    else:
        df["submitted_at"] = datetime.now(timezone.utc)
        
    # 3. Encontra response_id / token
    id_col = None
    for col in df.columns:
        col_norm = col.lower().strip()
        if "response id" in col_norm or "token" in col_norm or "id da resposta" in col_norm or "id" == col_norm:
            id_col = col
            break
            
    if id_col:
        df["response_id"] = df[id_col].astype(str)
    else:
        import hashlib
        df["response_id"] = df.apply(lambda r: hashlib.md5(f"{r['email']}_{r['submitted_at']}".encode('utf-8')).hexdigest(), axis=1)
        
    # 4. Formata as respostas em JSON
    records = []
    for idx, row in df.iterrows():
        answers_list = []
        for col in df.columns:
            if col in ("email", "submitted_at", "response_id", sub_col, id_col, email_col):
                continue
            val = row[col]
            if pd.isna(val) or str(val).strip() == "":
                continue
                
            ans_dict = {
                "field": {"id": col, "type": "text"},
                "type": "text",
                "text": str(val)
            }
            answers_list.append(ans_dict)
            
        records.append({
            "response_id":  row["response_id"],
            "form_id":      form_id,
            "submitted_at": row["submitted_at"],
            "email":        row["email"],
            "answers":      json.dumps(answers_list, ensure_ascii=False),
            "updated_at":   datetime.now(timezone.utc).isoformat()
        })
        
    return pd.DataFrame(records)

def main():
    engine = get_engine()
    analises_dir = Path("c:\\Users\\trafe\\OneDrive\\Desktop\\workspace-mmm\\analises")
    
    ac_dfs = []
    meta_dfs = []
    google_dfs = []
    tf_dfs = []
    
    for sub in sorted(analises_dir.iterdir()):
        if not sub.is_dir() or sub.name == 'calendario' or sub.name == '[PERPETUO]':
            continue
            
        period = LAUNCH_PERIODS.get(sub.name)
        print(f"\nMapeando arquivos historicos para: {sub.name} (Periodo Google Ads: {period})")
        
        # 1. Active Campaign
        ac_dir = sub / "Active Campaign"
        if ac_dir.exists():
            # Pega o primeiro ou o que tem "active-campaign"
            ac_csvs = list(ac_dir.glob("active-campaign*.csv"))
            if not ac_csvs:
                ac_csvs = list(ac_dir.glob("*.csv"))
            if ac_csvs:
                print(f"  - AC: Carregando {ac_csvs[0].name}...")
                try:
                    df = load_ac_csv(str(ac_csvs[0]))
                    ac_dfs.append(df)
                except Exception as e:
                    print(f"    [ERRO] AC {ac_csvs[0].name}: {e}")
                    
        # 2. Meta Ads
        meta_dir = sub / "Meta Ads"
        if meta_dir.exists():
            meta_csvs = list(meta_dir.glob("meta*.csv"))
            if not meta_csvs:
                meta_csvs = list(meta_dir.glob("*.csv"))
            if meta_csvs:
                print(f"  - Meta: Carregando {meta_csvs[0].name}...")
                try:
                    df = load_meta_csv(str(meta_csvs[0]))
                    meta_dfs.append(df)
                except Exception as e:
                    print(f"    [ERRO] Meta {meta_csvs[0].name}: {e}")
                    
        # 3. Google Ads
        google_dir = sub / "Google Ads"
        if google_dir.exists() and period:
            # Pega o CSV de performance DOS anuncios
            google_csvs = [
                c for c in google_dir.glob("*.csv")
                if any(x in c.name.lower() for x in ["dos-anuncios", "dos anuncios", "dos anúncios"])
            ]
            if not google_csvs:
                google_csvs = list(google_dir.glob("*.csv"))
            if google_csvs:
                print(f"  - Google: Carregando {google_csvs[0].name}...")
                try:
                    df = load_google_csv(str(google_csvs[0]), period)
                    google_dfs.append(df)
                except Exception as e:
                    print(f"    [ERRO] Google {google_csvs[0].name}: {e}")
                    
        # 4. Typeform
        tf_dir = sub / "Typeform"
        if tf_dir.exists():
            tf_csvs = list(tf_dir.glob("*pesquisa*.csv"))
            if not tf_csvs:
                tf_csvs = list(tf_dir.glob("*.csv"))
            if tf_csvs:
                # Usa o nome da pasta de lancamento como form_id
                form_id = sub.name.replace('[', '').replace(']', '')
                print(f"  - Typeform: Carregando {tf_csvs[0].name} (form_id: {form_id})...")
                try:
                    df = load_typeform_csv(tf_csvs[0], form_id)
                    tf_dfs.append(df)
                except Exception as e:
                    print(f"    [ERRO] Typeform {tf_csvs[0].name}: {e}")

    # --- Salvar dados no Supabase ---
    print("\n" + "="*50)
    print("Iniciando gravacao consolidada no Supabase...")
    print("="*50)
    
    # 1. Active Campaign (leads)
    if ac_dfs:
        df_ac_all = pd.concat(ac_dfs).drop_duplicates(subset=["id"])
        print(f"\n[AC/Leads] Gravando {len(df_ac_all)} leads...")
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE leads RESTART IDENTITY CASCADE"))
        df_ac_all.to_sql("leads", engine, if_exists="append", index=False, method="multi", chunksize=500)
        print("  [OK] Leads gravados com sucesso!")
        
    # 2. Meta Ads
    if meta_dfs:
        df_meta_all = pd.concat(meta_dfs).drop_duplicates(subset=["ad_id", "date", "lancamento_codigo"])
        print(f"\n[Meta Ads] Gravando {len(df_meta_all)} registros diarios...")
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE meta_ads_daily RESTART IDENTITY CASCADE"))
        df_meta_all.to_sql("meta_ads_daily", engine, if_exists="append", index=False, method="multi", chunksize=500)
        print("  [OK] Meta Ads gravado com sucesso!")
        
    # 3. Google Ads
    if google_dfs:
        df_google_all = pd.concat(google_dfs).drop_duplicates(subset=["ad_id", "date"])
        print(f"\n[Google Ads] Gravando {len(df_google_all)} registros diarios...")
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE google_ads_daily RESTART IDENTITY CASCADE"))
        # Garante updated_at preenchido se faltar
        df_google_all["updated_at"] = datetime.now(timezone.utc).isoformat()
        df_google_all.to_sql("google_ads_daily", engine, if_exists="append", index=False, method="multi", chunksize=500)
        print("  [OK] Google Ads gravado com sucesso!")
        
    # 4. Typeform
    if tf_dfs:
        df_tf_all = pd.concat(tf_dfs).drop_duplicates(subset=["response_id"])
        print(f"\n[Typeform] Gravando {len(df_tf_all)} respostas...")
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE typeform_respostas RESTART IDENTITY CASCADE"))
        df_tf_all.to_sql("typeform_respostas", engine, if_exists="append", index=False, method="multi", chunksize=500)
        print("  [OK] Typeform gravado com sucesso!")

    print("\nExecutando migração retroativa e atualização de lancamento_codigo...")
    try:
        run_migration()
        print("  [OK] Migração e atribuição de lançamentos concluídas!")
    except Exception as e:
        print(f"  [ERRO] Falha ao rodar migração: {e}")

    print("\nBase historica importada com sucesso para todas as fontes!")

if __name__ == '__main__':
    main()
