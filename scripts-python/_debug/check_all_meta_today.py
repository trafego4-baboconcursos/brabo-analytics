import os
import datetime

base_path = r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm\analises"
print("=== BUSCA POR ARQUIVOS META EM TODAS AS PASTAS MODIFICADOS HOJE ===")
for root, dirs, files in os.walk(base_path):
    for f in files:
        if "meta" in f.lower():
            p = os.path.join(root, f)
            stat = os.stat(p)
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
            # Verifica se foi modificado hoje (2026-06-11)
            if mtime.date() == datetime.date(2026, 6, 11):
                print(f"File: {os.path.relpath(p, base_path)} | Size: {stat.st_size} bytes | Modified: {mtime}")
