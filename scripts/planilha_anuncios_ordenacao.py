"""Planilha "Anúncios - [LANC]" do Drive: aba VENDAS + vendas por busca + seletor de ordenação.

Cria a aba VENDAS a partir das vendas das abas FB/YT, troca as colunas de vendas digitadas por busca
na VENDAS pelo ADxxx, passa F/G da principal para ARRAYFORMULA, faz as colunas do Google buscarem por
prefixo e põe em B2 (principal, FB, YT) a lista "Ordenar: Vendas / ROAS / Investimento / Leads".
Padrão em docs/performance/playbooks/PADRAO_PLANILHAS_LANCAMENTO.md.

Confira antes que as vendas da principal batem com as abas FB/YT — o script copia das abas FB/YT.
Sem --apply só simula. Faz backup das três abas em outputs/backups/ antes de gravar.

    python scripts/planilha_anuncios_ordenacao.py <SPREADSHEET_ID> <LANC> <TICKET> [--apply]
    python scripts/planilha_anuncios_ordenacao.py 164ZInfi... PI-AGO-26 1635,18
"""
import os, requests, sys, time, csv
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
SID, L, TICKET = sys.argv[1], sys.argv[2], sys.argv[3]
APPLY = "--apply" in sys.argv
tok = requests.post("https://oauth2.googleapis.com/token", data={
    "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"], "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    "refresh_token": os.environ["GOOGLE_SHEETS_REFRESH_TOKEN"], "grant_type": "refresh_token"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
BASE = f"https://sheets.googleapis.com/v4/spreadsheets/{SID}"
P, FB, YT = f"'Anúncios [{L}]'", f"' Anúncios FB [{L}]'", f"'Anúncios YT [{L}]'"
OPC = ["Ordenar: Vendas", "Ordenar: ROAS", "Ordenar: Investimento", "Ordenar: Leads"]


def get(r, f="FORMATTED_VALUE"):
    return requests.get(f"{BASE}/values/{r}", params={"valueRenderOption": f}, headers=H).json().get("values", [])


def put(r, v):
    requests.put(f"{BASE}/values/{r}", params={"valueInputOption": "USER_ENTERED"}, headers=H, json={"values": v}).raise_for_status()


def clear(r):
    requests.post(f"{BASE}/values/{r}:clear", headers=H).raise_for_status()


def batch(reqs):
    x = requests.post(f"{BASE}:batchUpdate", headers=H, json={"requests": reqs})
    x.raise_for_status()
    return x.json()


def toi(s):
    s = str(s).replace(".", "").strip()
    return int(s) if s.isdigit() else 0


def cod(n):
    return n[:5] if n.startswith("AD") else n


sheets = {s["properties"]["title"]: s["properties"]["sheetId"]
          for s in requests.get(BASE, params={"fields": "sheets.properties"}, headers=H).json()["sheets"]}


def sid_of(a):
    return sheets[a.strip("'")]


# --- dados da aba VENDAS (das abas FB/YT, que estão alinhadas) ---
# linha sem anúncio (lista vazia = "#N/A") não entra: a venda ao lado é resto do lançamento copiado
pr = [r for r in get(f"{P}!A4:X200") if r and r[0] and not r[0].startswith("#")]
fb = {cod(r[0]): (r[0], toi(r[5])) for r in get(f"{FB}!A4:F200") if len(r) > 5 and r[0] and not r[0].startswith("#")}
yt = {cod(r[0]): (r[0], toi(r[5])) for r in get(f"{YT}!A4:F200") if len(r) > 5 and r[0] and not r[0].startswith("#")}
tk = {cod(r[0]): toi(r[23]) for r in pr if len(r) > 23}
nomes = {}
for r in pr:
    nomes.setdefault(cod(r[0]), r[0])
for d in (fb, yt):
    for c, (n, _) in d.items():
        nomes.setdefault(c, n)
linhas = sorted(([n, fb.get(c, ("", 0))[1] or "", yt.get(c, ("", 0))[1] or "", tk.get(c, 0) or ""] for c, n in nomes.items()),
                key=lambda l: -((l[1] or 0) + (l[2] or 0)))
print(f"VENDAS: {len(linhas)} linhas | FB {sum(l[1] or 0 for l in linhas)} | YT {sum(l[2] or 0 for l in linhas)} | TK {sum(l[3] or 0 for l in linhas)}")

# --- fórmulas ---
CH = ('  roas; ARRAYFORMULA(IFERROR(' + TICKET + ' * {v} / {i}; 0));\n'
      '  criterio; $B$2;\n'
      '  chave; IF(criterio = "Ordenar: ROAS"; roas; IF(criterio = "Ordenar: Investimento"; {i}; '
      'IF(criterio = "Ordenar: Leads"; {l}; {v})));\n')


def vendas_key(col):
    return (f'  vendas_total; MAP(cod_unicos; LAMBDA(c; VALUE(IFERROR(SUMIFS(VENDAS!{col}:{col}; VENDAS!A:A; '
            f'IF(LEFT(c;2)="AD"; c & "*"; c)); 0))));\n'
            '  vendas_filtrados; FILTER(vendas_total; investimento_total > 0);\n')


novoA = {}
for aba, col in ((P, "B"), (FB, "C")):
    A4 = get(f"{aba}!A4", "FORMULA")[0][0]
    old = "cod_ordenados; SORT(cod_filtrados; leads_filtrados; FALSE);"
    assert old in A4 and "criterio" not in A4, f"{aba}: A4 fora do modelo ou seletor já aplicado"
    novoA[aba] = A4.replace(old, "invest_filtrados; FILTER(investimento_total; investimento_total > 0);\n" + vendas_key(col)
                            + CH.format(v="vendas_filtrados", i="invest_filtrados", l="leads_filtrados")
                            + "  \n  cod_ordenados; SORT(cod_filtrados; chave; FALSE; leads_filtrados; FALSE);")
A4 = get(f"{YT}!A4", "FORMULA")[0][0]
old = "  matriz_ordenada; SORT({cod_unicos \\ leads}; 2; 0);\n  cod_ordenados; INDEX(matriz_ordenada; 0; 1);"
assert old in A4 and "criterio" not in A4, "YT A4 diferente do esperado"
novoA[YT] = A4.replace(old,
    "  invest; MAP(cod_unicos; LAMBDA(c; VALUE(SUMIF('EXTRACAO-GA'!A:A; c & \"*\"; 'EXTRACAO-GA'!C:C))));\n"
    "  vendas; MAP(cod_unicos; LAMBDA(c; VALUE(IFERROR(SUMIFS(VENDAS!D:D; VENDAS!A:A; c & \"*\"); 0))));\n"
    + CH.format(v="vendas", i="invest", l="leads") + "  \n  cod_ordenados; SORT(cod_unicos; chave; FALSE; leads; FALSE);")


def busca(aba_ext, col):
    return ('=MAP(A4:A; LAMBDA(nome; IF(nome=""; ""; SUMIFS(%s!%s:%s; %s!A:A; '
            'IF(LEFT(nome;2)="AD"; LEFT(nome; 5) & "*"; nome)))))' % (aba_ext, col, col, aba_ext))


def busca_yt(col):
    return ("=MAP(A4:A; LAMBDA(anuncio; IF(anuncio=\"\"; \"\"; SUMIFS('EXTRACAO-GA'!%s:%s; 'EXTRACAO-GA'!A:A; "
            "LEFT(anuncio; 5) & \"*\"))))" % (col, col))


antes = {a: get(f"{a}!C2:H2", "UNFORMATTED_VALUE") for a in (P, FB, YT)}
print("totais antes:", antes)
if not APPLY:
    sys.exit("[dry-run] nada gravado")

# backup
os.makedirs("outputs/backups", exist_ok=True)
for a in (P, FB, YT):
    for f in ("FORMATTED_VALUE", "FORMULA"):
        nome = f"outputs/backups/backup_planilha_anuncios_{L}_sid{sid_of(a)}_{f.lower()}_{time.strftime('%Y%m%d')}.csv"
        with open(nome, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(get(f"{a}!A1:Z200", f))
# 1) aba VENDAS
if "VENDAS" not in sheets:
    r = batch([{"addSheet": {"properties": {"title": "VENDAS", "gridProperties": {"frozenRowCount": 1}}}}])
    sheets["VENDAS"] = r["replies"][0]["addSheet"]["properties"]["sheetId"]
clear("VENDAS!A1:E")
put(f"VENDAS!A1:E{len(linhas)+1}", [["Criativo", "Vendas Totais", "Vendas FB", "Vendas YT", "Vendas TK"]]
    + [[l[0], "", l[1], l[2], l[3]] for l in linhas])
put("VENDAS!B2", [['=ARRAYFORMULA(IF(A2:A=""; ""; C2:C + D2:D + E2:E))']])
batch([{"repeatCell": {"range": {"sheetId": sheets["VENDAS"], "startRowIndex": 0, "endRowIndex": 1},
                       "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}}, "fields": "userEnteredFormat.textFormat.bold"}}])
# 2) vendas por busca + F/G em ARRAYFORMULA + Google por prefixo
for col, src in (("L", "C"), ("R", "D"), ("X", "E")):
    clear(f"{P}!{col}4:{col}")
    put(f"{P}!{col}4", [[busca("VENDAS", src)]])
clear(f"{P}!F4:G")
put(f"{P}!F4:G4", [['=ARRAYFORMULA(IF(A4:A=""; ""; L4:L + R4:R + X4:X))', '=ARRAYFORMULA(IF(A4:A=""; ""; IFERROR(C4:C / F4:F; "-")))']])
put(f"{P}!O4:P4", [[busca("'EXTRACAO-GA'", "C"), busca("'EXTRACAO-GA'", "D")]])
clear(f"{FB}!F4:F")
put(f"{FB}!F4", [[busca("VENDAS", "C")]])
clear(f"{YT}!F4:F")
put(f"{YT}!F4", [[busca("VENDAS", "D")]])
put(f"{YT}!C4:D4", [[busca_yt("C"), busca_yt("D")]])
# 3) seletor
reqs = []
for a in (P, FB, YT):
    rng = {"sheetId": sid_of(a), "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 1, "endColumnIndex": 2}
    reqs += [{"setDataValidation": {"range": rng, "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": o} for o in OPC]},
                                                           "strict": True, "showCustomUi": True}}},
             {"repeatCell": {"range": rng, "cell": {"userEnteredFormat": {"textFormat": {"fontFamily": "Roboto", "fontSize": 11, "bold": True},
              "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}},
              "fields": "userEnteredFormat(textFormat.fontFamily,textFormat.fontSize,textFormat.bold,horizontalAlignment,verticalAlignment,wrapStrategy)"}}]
batch(reqs)
for a in (P, FB, YT):
    put(f"{a}!B2", [[OPC[0]]])
    put(f"{a}!A4", [[novoA[a]]])
time.sleep(4)
# conferência
for a in (P, FB, YT):
    print("==", a, "\n  totais antes:", antes[a], "\n  totais depois:", get(f"{a}!C2:H2", "UNFORMATTED_VALUE"))
    for opc, col in (("Ordenar: ROAS", 7), ("Ordenar: Investimento", 2), ("Ordenar: Leads", 3), ("Ordenar: Vendas", 5)):
        put(f"{a}!B2", [[opc]])
        time.sleep(3)
        v = [r for r in get(f"{a}!A4:H200", "UNFORMATTED_VALUE") if r and r[0]]
        vals = [float(r[col]) if len(r) > col and isinstance(r[col], (int, float)) else 0 for r in v]
        ok = all(vals[i] <= vals[i-1] + 0.005 for i in range(1, len(vals)))
        print(f"  {opc:22} ordenado: {ok} {[r[0][:5] for r in v[:3]]} ({len(v)})")
    print("  erros:", [c for r in get(f"{a}!A4:X200") for c in r if str(c).startswith("#")][:5])
pv = [r for r in get(f"{P}!A4:X200", "UNFORMATTED_VALUE") if r and r[0]]
print("principal F == L+R+X em todas:", all(r[5] == (r[11] or 0) + (r[17] or 0) + (r[23] or 0) for r in pv))
