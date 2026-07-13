import os

base_path = r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm"
print("=== BUSCA POR ARQUIVOS COM 'META' OU 'CSV' NOVOS ===")
for root, dirs, files in os.walk(base_path):
    if ".venv" in root or ".vscode" in root or ".claude" in root or "node_modules" in root:
        continue
    for f in files:
        if "meta" in f.lower() or f.endswith('.csv'):
            full_path = os.path.join(root, f)
            print(f"File: {os.path.relpath(full_path, base_path)} | Size: {os.path.getsize(full_path)} bytes")
