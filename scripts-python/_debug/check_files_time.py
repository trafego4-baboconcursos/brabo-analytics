import os
import datetime

base_path = r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm\analises\[PERPETUO]"

print("=== LISTA DE ARQUIVOS EM [PERPETUO] ===")
for root, dirs, files in os.walk(base_path):
    for f in files:
        full_path = os.path.join(root, f)
        stat = os.stat(full_path)
        mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
        print(f"File: {os.path.relpath(full_path, base_path)} | Size: {stat.st_size} bytes | Modified: {mtime}")
