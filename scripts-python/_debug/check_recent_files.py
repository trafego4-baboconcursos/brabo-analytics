import os
import datetime

base_path = r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm"
now = datetime.datetime.now()

print("=== BUSCA POR ARQUIVOS ATUALIZADOS RECENTEMENTE ===")
for root, dirs, files in os.walk(base_path):
    if ".venv" in root or ".vscode" in root or ".claude" in root or "node_modules" in root:
        continue
    for f in files:
        full_path = os.path.join(root, f)
        stat = os.stat(full_path)
        mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
        diff = now - mtime
        if diff.total_seconds() < 600: # 10 minutos
            print(f"RECENT: {os.path.relpath(full_path, base_path)} | Size: {stat.st_size} bytes | Modified: {mtime}")
