import os
import sys
import re
import unicodedata
import argparse
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from db import get_users_engine

load_dotenv()

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

def normalize_header(col: str) -> str:
    col = str(col).lower().strip()
    col = unicodedata.normalize('NFKD', col).encode('ascii', 'ignore').decode('ascii')
    
    # Substituicoes de caracteres e normalizacao para snake_case
    col = col.replace('do(a)', '_do_a_')
    col = col.replace('de(a)', '_de_a_')
    col = col.replace('do(s)', '_do_s_')
    col = col.replace('de(s)', '_de_s_')
    col = col.replace('o(a)', '_o_a_')
    col = col.replace('a(a)', '_a_a_')
    col = col.replace('(a)', '_a_')
    col = col.replace('(s)', '_s_')
    col = col.replace(' / ', '_')
    col = col.replace('/', '_')
    col = col.replace(' - ', '_')
    col = col.replace('-', '_')
    col = col.replace('  ', ' ')
    col = col.replace(' ', '_')
    col = re.sub(r'[^a-z0-9_]', '', col)
    col = re.sub(r'_+', '_', col)
    col = col.strip('_')
    return col

def parse_money(value) -> float:
    if pd.isna(value):
        return 0.0
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "(none)"}:
        return 0.0
    text = re.sub(r"[^0-9,.-]", "", text)
    if not text or text in {"-", ".", ","}:
        return 0.0
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    return float(pd.to_numeric(text, errors="coerce") or 0.0)

def main():
    parser = argparse.ArgumentParser(description="Importa vendas Hotmart/TMB para as tabelas oficiais.")
    parser.add_argument("--launch-code", metavar="CODE", help="Importa apenas um lancamento especifico")
    args = parser.parse_args()

    engine = get_users_engine()
    inspector = inspect(engine)
    
    # Obter colunas existentes nas tabelas oficiais do Supabase
    hm_cols = [c['name'] for c in inspector.get_columns('hotmart_clean_oficial')]
    tmb_cols = [c['name'] for c in inspector.get_columns('tmb_clean_oficial')]
    
    if not hm_cols or not tmb_cols:
        print("Erro: Nao foi possivel obter as colunas de hotmart_clean_oficial ou tmb_clean_oficial. Verifique a conexao.")
        sys.exit(1)
        
    analises_dir = Path(__file__).parent.parent / "analises"
    
    total_hm = 0
    total_tmb = 0
    
    for sub in sorted(analises_dir.iterdir()):
        if not sub.is_dir() or sub.name == 'calendario':
            continue
        launch_code = sub.name.strip("[]")
        if args.launch_code and launch_code.upper() != args.launch_code.upper():
            continue

        # Buscar tmb_produto_ids do launch_config para popular lancamento_id nas linhas TMB
        tmb_lancamento_id = None
        try:
            with engine.connect() as conn:
                cfg_row = conn.execute(
                    text("SELECT tmb_produto_ids FROM launch_config WHERE lancamento_codigo = :code"),
                    {"code": launch_code},
                ).fetchone()
            if cfg_row and cfg_row[0]:
                # tmb_produto_ids é text[] no PostgreSQL → chega como list Python
                ids_val = cfg_row[0]
                if isinstance(ids_val, list):
                    first = ids_val[0] if ids_val else None
                else:
                    first = str(ids_val).strip().strip("[]'\"")
                try:
                    tmb_lancamento_id = int(first) if first else None
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            print(f"  Aviso: nao foi possivel ler launch_config para {launch_code}: {e}")

        vendas_dir = sub / "vendas"
        if not vendas_dir.exists():
            vendas_dir = sub / "Vendas"
            
        if not vendas_dir.exists():
            continue
            
        print(f"\nProcessando lancamento: {sub.name}")
        
        # 1. Hotmart
        hm_csv = None
        for csv in vendas_dir.glob("*.csv"):
            if "hotmart" in csv.name.lower():
                hm_csv = csv
                break
                
        if hm_csv:
            enc = _detect_encoding(hm_csv)
            sep = _detect_separator(hm_csv, enc)
            try:
                df = pd.read_csv(hm_csv, sep=sep, encoding=enc, dtype=str)
                # Normaliza colunas
                df.columns = [normalize_header(c) for c in df.columns]
                
                # Mapeamento adicional para compatibilidade
                if 'faturamento_liquido' not in df.columns and 'faturamento_liquido_do_a_produtor_a' in df.columns:
                    df['faturamento_liquido'] = df['faturamento_liquido_do_a_produtor_a']
                if 'email_do_a_comprador_a' not in df.columns and 'email' in df.columns:
                    df['email_do_a_comprador_a'] = df['email']
                if 'comprador_a' not in df.columns and 'nome' in df.columns:
                    df['comprador_a'] = df['nome']
                if 'status_da_transacao' not in df.columns and 'status' in df.columns:
                    df['status_da_transacao'] = df['status']
                
                # Converter tipos de dados numericos
                numeric_cols = [
                    'valor_de_compra_com_impostos', 'valor_de_compra_sem_impostos',
                    'faturamento_bruto_sem_impostos', 'faturamento_liquido',
                    'faturamento_liquido_do_a_produtor_a', 'taxa_de_processamento'
                ]
                for c in numeric_cols:
                    if c in df.columns:
                        df[c] = df[c].apply(parse_money)
                        
                int_cols = ['codigo_do_produto', 'quantidade_total_de_parcelas', 'quantidade_de_cobrancas', 'quantidade_de_itens']
                for c in int_cols:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
                        
                if 'tax_solutions' in df.columns:
                    df['tax_solutions'] = df['tax_solutions'].astype(str).str.lower().map({'true': True, '1': True, 'yes': True}).fillna(False)
                
                # Garante colunas da tabela Supabase
                for c in hm_cols:
                    if c not in df.columns:
                        df[c] = None
                        
                df_to_save = df[hm_cols]
                
                # Deleta transacoes do CSV atual antes de inserir para evitar duplicacao
                transaction_ids = df_to_save['codigo_da_transacao'].dropna().unique().tolist()
                if transaction_ids:
                    with engine.begin() as conn:
                        conn.execute(
                            text("DELETE FROM hotmart_clean_oficial WHERE codigo_da_transacao = ANY(:ids)"),
                            {"ids": transaction_ids}
                        )
                
                # Grava
                df_to_save.to_sql('hotmart_clean_oficial', engine, if_exists='append', index=False, method='multi', chunksize=500)
                print(f"  - Hotmart: {len(df_to_save)} registros importados.")
                total_hm += len(df_to_save)
            except Exception as e:
                print(f"  - Hotmart: Erro ao importar {hm_csv.name}: {e}")
                
        # 2. TMB
        tmb_csv = None
        for csv in vendas_dir.glob("*.csv"):
            if "tmb" in csv.name.lower():
                tmb_csv = csv
                break
                
        if tmb_csv:
            enc = _detect_encoding(tmb_csv)
            sep = _detect_separator(tmb_csv, enc)
            try:
                df = pd.read_csv(tmb_csv, sep=sep, encoding=enc, dtype=str)
                df.columns = [normalize_header(c) for c in df.columns]
                
                # Mapeamentos para TMB Oficial
                tmb_mapping = {
                    'id_do_pedido': 'pedido',
                    'pedido': 'pedido',
                    'nome_do_produto': 'produto',
                    'produto': 'produto',
                    'nome_da_oferta': 'oferta',
                    'oferta': 'oferta',
                    'status_pedido': 'status',
                    'situao': 'status',
                    'status': 'status',
                    'forma_de_pagamento': 'forma_pagamento',
                    'forma_pagamento': 'forma_pagamento',
                    'nome_do_cliente': 'nome_cliente',
                    'nome_cliente': 'nome_cliente',
                    'e_mail_do_cliente': 'email_cliente',
                    'email_cliente': 'email_cliente',
                    'cliente_email': 'email_cliente',
                    'cpf_cliente': 'cpf_cliente',
                    'cpf_do_cliente': 'cpf_cliente',
                    'telefone_do_cliente': 'telefone',
                    'telefone': 'telefone',
                    'cidade': 'cidade',
                    'estado': 'estado',
                    'utm_source': 'utm_source',
                    'utm_medium': 'utm_medium',
                    'utm_campaign': 'utm_campaign'
                }
                for k, v in tmb_mapping.items():
                    if k in df.columns and v not in df.columns:
                        df[v] = df[k]
                
                # Tratamento especial de ticket do pedido para valor_liquido
                if 'ticket_do_pedido' in df.columns and 'valor_liquido' not in df.columns:
                    df['valor_liquido'] = df['ticket_do_pedido']
                if 'valor_liquido' in df.columns:
                    df['valor_liquido'] = df['valor_liquido'].apply(parse_money)
                
                # Tratamento especial de data
                if 'data_efetivado' in df.columns:
                    df['data_efetivado'] = pd.to_datetime(df['data_efetivado'], errors='coerce', dayfirst=True)
                elif 'criado_em' in df.columns:
                    df['data_efetivado'] = pd.to_datetime(df['criado_em'], errors='coerce', dayfirst=True)
                
                # Garante colunas do Supabase
                for c in tmb_cols:
                    if c not in df.columns:
                        df[c] = None

                if tmb_lancamento_id and 'lancamento_id' in tmb_cols:
                    df['lancamento_id'] = tmb_lancamento_id

                df_to_save = df[tmb_cols]
                
                # Deleta pedidos do CSV atual antes de inserir para evitar duplicacao
                order_ids = df_to_save['pedido'].dropna().unique().tolist()
                if order_ids:
                    with engine.begin() as conn:
                        conn.execute(
                            text("DELETE FROM tmb_clean_oficial WHERE pedido = ANY(:ids)"),
                            {"ids": [str(x) for x in order_ids]}
                        )
                
                # Grava
                df_to_save.to_sql('tmb_clean_oficial', engine, if_exists='append', index=False, method='multi', chunksize=500)
                print(f"  - TMB: {len(df_to_save)} registros importados.")
                total_tmb += len(df_to_save)
            except Exception as e:
                print(f"  - TMB: Erro ao importar {tmb_csv.name}: {e}")
 
    print(f"\nImportacao concluida! Total Hotmart: {total_hm} | Total TMB: {total_tmb}")
 
if __name__ == '__main__':
    main()
