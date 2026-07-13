import os
import sys
from pathlib import Path
from sqlalchemy import text
from db import get_engine

BASE_DIR = Path(__file__).parent

def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'replace').decode('ascii'))

def main():
    try:
        engine = get_engine()
        
        # Le o arquivo schema.sql
        with open(BASE_DIR / "schema.sql", "r", encoding="utf-8") as f:
            sql_script = f.read()
            
        safe_print("Executando criacao das tabelas no Supabase...")
        
        # Limpa comentarios em bloco /* */
        import re
        sql_clean = re.sub(r'/\*.*?\*/', '', sql_script, flags=re.DOTALL)
        
        # Limpa comentarios de linha unica -- para evitar que ponto-e-virgula nos comentarios quebre o split
        sql_clean = re.sub(r'--.*$', '', sql_clean, flags=re.MULTILINE)
        
        with engine.begin() as conn:
            try:
                # Executa o script inteiro de uma vez para suportar funções PL/pgSQL
                conn.execute(text(sql_script))
            except Exception as e:
                safe_print(f"Erro ao executar script: {repr(e)}")
                raise e
                    
        safe_print("Tabelas e views criadas/verificadas com sucesso no Supabase!")
        
    except Exception as e:
        safe_print(f"Erro geral de execucao: {repr(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
