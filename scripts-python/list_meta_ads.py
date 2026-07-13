import os
import datetime

folder = r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm\analises\[PERPETUO]\meta-ads"
print(f"=== LISTANDO ARQUIVOS EM: {folder} ===")
if os.path.exists(folder):
    for f in os.listdir(folder):
        p = os.path.join(folder, f)
        stat = os.stat(p)
        print(f"File: {f} | Size: {stat.st_size} bytes | Modified: {datetime.datetime.fromtimestamp(stat.st_mtime)}")
else:
    print("Diretorio nao existe!")
