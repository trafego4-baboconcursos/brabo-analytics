import os
import datetime

base_path = r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm"

print("=== LISTA DE ARQUIVOS EXCEL E CSV NA RAIZ ===")
for root, dirs, files in os.walk(base_path):
    # Ignora pastas de ambiente virtual e git
    if ".venv" in root or ".vscode" in root or ".claude" in root or "node_modules" in root:
        continue
    for f in files:
        if f.endswith('.xlsx') or f.endswith('.csv'):
            full_path = os.path.join(root, f)
            stat = os.stat(full_path)
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
            print(f"File: {os.path.relpath(full_path, base_path)} | Size: {stat.st_size} bytes | Modified: {mtime}")
