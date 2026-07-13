import os
import datetime

base_path = r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm"
today = datetime.date(2026, 6, 11)

print("=== BUSCA POR TODAS AS PLANILHAS MODIFICADAS HOJE ===")
for root, dirs, files in os.walk(base_path):
    if ".venv" in root or ".vscode" in root or ".claude" in root or "node_modules" in root:
        continue
    for f in files:
        if f.endswith('.xlsx') or f.endswith('.xls') or f.endswith('.csv'):
            p = os.path.join(root, f)
            stat = os.stat(p)
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
            if mtime.date() == today:
                print(f"File: {os.path.relpath(p, base_path)} | Size: {stat.st_size} bytes | Modified: {mtime}")
