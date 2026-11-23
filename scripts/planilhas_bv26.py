"""Planilhas do Drive da BV-26 (Verba Diária, Captação, Anúncios) preenchidas pelo banco, não pelo Stract.

As três planilhas nasceram em 05/10/26 como cópia crua das da BV-25 (abas, fórmulas e dados de 2025). As fórmulas da
BV-25 procuram campanha pelo nome antigo (`[M] [CADASTRO] Captação INSS…`) e anúncio por código fixo em cada célula, então
não dá para só trocar o código. Este script recria as abas:

- `EXTRACAO-BM` / `EXTRACAO-GA`: uma linha por dia × anúncio, de `meta_ads_daily` / `google_ads_daily`, já com expert,
  etapa, público e formato lidos do nome da campanha (NOMENCLATURA_BV-26). É a mesma extração nas três planilhas.
- Abas de relatório com fórmulas `SUMIFS` sobre essas colunas (nada de nome de campanha dentro da fórmula).
- `VENDAS` (Anúncios): comprador × ADxxx do utm_term do cadastro; `Grupos` (Captação): tabela `BV_26` dos grupos.

Rodar de novo atualiza tudo (as abas de extração são limpas, não apagadas, para não quebrar as fórmulas).
Sem --apply só mostra o que vai gravar.

    python scripts/planilhas_bv26.py [--apply]
"""
import datetime as dt
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import text

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")
sys.path.insert(0, str(RAIZ))
from etl.db import get_engine  # noqa: E402
from frontend.db_readers.sales import _read_vendas_uncached  # noqa: E402

APPLY = "--apply" in sys.argv
L = "BV-26"
PLANILHAS = {
    "verba": "1yl5x3uCSVyCBV3D7sRD-HuW4uw4kO1nt3PxqEwY4lHU",
    "captacao": "1VEL3DaYO_YjWtu5ne_PnFc2F4wXM4Va8ghSR2nYv4uM",
    "anuncios": "1lIdY8HGdB1eScG1M4C6SCzOVRnMU3iEnOMW3q_IM_Vk",
}
EXPERTS = ["Mateus", "Ivan", "Felipe"]
ETAPAS = ["Aquecimento", "Base Forte", "Captação", "Lembrete", "Matrículas"]
PUBLICOS = ["Aluno", "Super Quente"]
BM, GA = "EXTRACAO-BM", "EXTRACAO-GA"
PLAT = {"Facebook": BM, "Google": GA}

# ORCAMENTO_BV-26 §4 (plano por etapa × expert × plataforma) e §6 (captação por expert e dia)
PLANO = {
    ("Aquecimento", "Mateus"): (11537.50, 4712.50), ("Aquecimento", "Ivan"): (7488.00, 4212.00),
    ("Aquecimento", "Felipe"): (2366.00, 2184.00),
    ("Base Forte", "Mateus"): (11537.50, 4712.50), ("Base Forte", "Ivan"): (7488.00, 4212.00),
    ("Base Forte", "Felipe"): (2366.00, 2184.00),
    ("Captação", "Mateus"): (69220.00, 28280.00), ("Captação", "Ivan"): (45760.00, 25740.00),
    ("Captação", "Felipe"): (13520.00, 12480.00),
    ("Lembrete", "Mateus"): (7100.00, 2900.00), ("Lembrete", "Ivan"): (4694.00, 2640.00),
    ("Lembrete", "Felipe"): (1386.00, 1280.00),
    ("Matrículas", "Mateus"): (3550.00, 1450.00), ("Matrículas", "Ivan"): (2347.00, 1320.00),
    ("Matrículas", "Felipe"): (693.00, 640.00),
}
WHATSAPP, RESERVA = 153700.00, 6300.00
CURVA_DIA = {  # verba da captação por dia (total) e por expert, §6
    dt.date(2026, 10, 5): (27800, 13900, 10200, 3700), dt.date(2026, 10, 6): (27900, 14000, 10200, 3700),
    dt.date(2026, 10, 7): (22300, 11200, 8200, 3000), dt.date(2026, 10, 8): (20400, 10200, 7500, 2700),
    dt.date(2026, 10, 9): (18600, 9300, 6800, 2500), dt.date(2026, 10, 10): (11100, 5600, 4100, 1500),
    dt.date(2026, 10, 11): (9300, 4600, 3400, 1200), dt.date(2026, 10, 12): (22300, 11200, 8200, 3000),
    dt.date(2026, 10, 13): (20400, 10200, 7500, 2700), dt.date(2026, 10, 14): (14900, 7400, 5500, 2000),
}
SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

# ---------------------------------------------------------------- classificação pelo nome (NOMENCLATURA_BV-26)

def classifica(campanha: str) -> tuple[str, str, str, str]:
    n = (campanha or "").lower()
    # [M]/[I]/[F] é a tag de expert de antes de 23/09; [TR] (trio sem expert) fica "Sem expert"
    expert = next((e for e in EXPERTS if f"[{e.lower()}]" in n or f"[{e[0].lower()}]" in n), "Sem expert")
    if "base forte" in n or "base-forte" in n:
        etapa = "Base Forte"
    elif "[aquecimento]" in n:
        etapa = "Aquecimento"
    elif "[lembrete]" in n:
        etapa = "Lembrete"
    elif "matrícula" in n or "matricula" in n:
        etapa = "Matrículas"
    elif "captação" in n or "captacao" in n:
        etapa = "Captação"
    else:
        etapa = "Outros"
    publico = "Super Quente" if ("super quente" in n or "super-quente" in n) else "Aluno" if "[aluno" in n else "Outros"
    formato = next((f for f in ("trio", "carrossel", "imagem", "reels", "shorts", "principal") if f"[{f}]" in n), "outros")
    return expert, etapa, publico, formato


RE_COD = re.compile(r"^\s*(ADC?-[A-Z]{2}\d+|AD\d+)", re.I)


def codigo(nome: str) -> str:
    m = RE_COD.match(nome or "")
    return m.group(1).upper() if m else (nome or "").split(" - ")[0].strip()


def serial(d: dt.date) -> int:
    return (d - dt.date(1899, 12, 30)).days


# ---------------------------------------------------------------- dados

def carrega():
    eng = get_engine()
    with eng.connect() as c:
        meta = c.execute(text("""
            SELECT date, campaign_name, ad_name, SUM(spend), SUM(leads), SUM(link_clicks), SUM(impressions)
            FROM meta_ads_daily WHERE lancamento_codigo = :l OR campaign_name ILIKE '%[BV-26]%'
            GROUP BY 1,2,3 ORDER BY 1,2,3"""), {"l": L}).fetchall()
        goog = c.execute(text("""
            SELECT date, campaign_name, ad_name, SUM(cost), SUM(conversions), SUM(clicks), SUM(impressions)
            FROM google_ads_daily WHERE lancamento_codigo = :l OR campaign_name ILIKE '%[BV-26]%'
            GROUP BY 1,2,3 ORDER BY 1,2,3"""), {"l": L}).fetchall()
        utm = c.execute(text("""
            SELECT DISTINCT ON (lower(email)) lower(email), utm_source, utm_campaign, utm_term, utm_content
            FROM lead_utm_lancamento WHERE lancamento_codigo = :l
            ORDER BY lower(email), ultimo_visto_em DESC NULLS LAST"""), {"l": L}).fetchall()
        grupos = c.execute(text("""
            SELECT "DATA1", "GRUPO DA CAMPANHA", "NÚMERO", "LEAD ÚNICO" FROM "BV_26" ORDER BY "ID" """)).fetchall()

    def linhas(rows):
        out = []
        for d, camp, ad, gasto, leads, cliques, imp in rows:
            ex, et, pub, fmt = classifica(camp)
            grupo = "Cadastro" if et in ("Captação", "Base Forte") else et
            out.append([serial(d), camp, ad or "", codigo(ad), ex, et, pub, fmt,
                        round(float(gasto or 0), 2), round(float(leads or 0), 2), int(cliques or 0), int(imp or 0), grupo])
        return out

    vendas = _read_vendas_uncached(L)
    compradores = {e.lower().strip() for e in (vendas.emails_hotmart | vendas.emails_tmb) if e}
    ticket = round(vendas.total_receita / vendas.total_vendas, 2) if vendas.total_vendas else 0
    por_ad = defaultdict(int)
    for email, src, camp, term, content in utm:
        if email not in compradores:
            continue
        cod = RE_COD.match(term or "") or RE_COD.match(content or "")
        if not cod:
            continue
        cod = cod.group(1).upper()
        plat = "Google" if (src or "").lower() in ("google", "youtube") else "Facebook"
        ex = classifica(camp)[0]
        if ex == "Sem expert":
            ex = {"MA": "Mateus", "IV": "Ivan", "FE": "Felipe"}.get(cod.split("-")[-1][:2], "Sem expert")
        por_ad[(cod, ex, plat)] += 1
    vendas_rows = [[c, e, p, n] for (c, e, p), n in sorted(por_ad.items())]
    return linhas(meta), linhas(goog), vendas_rows, ticket, vendas, grupos


# ---------------------------------------------------------------- Sheets

class Planilha:
    def __init__(self, sid):
        self.sid = sid
        self.base = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}"
        tok = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"], "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_SHEETS_REFRESH_TOKEN"], "grant_type": "refresh_token"}).json()["access_token"]
        self.h = {"Authorization": f"Bearer {tok}"}
        self.fmt = []
        self.recarrega()

    def recarrega(self):
        r = requests.get(self.base, headers=self.h, params={"fields": "sheets.properties"})
        r.raise_for_status()
        self.abas = {s["properties"]["title"]: s["properties"] for s in r.json()["sheets"]}

    def batch(self, reqs):
        if reqs:
            r = requests.post(self.base + ":batchUpdate", headers=self.h, json={"requests": reqs})
            if not r.ok:
                raise SystemExit(f"Sheets batchUpdate: {r.status_code} {r.text[:500]}")
        self.recarrega()

    def aba(self, titulo, linhas, colunas, indice):
        """Cria a aba ou limpa a existente (limpar mantém o sheetId: fórmulas de outras abas continuam valendo)."""
        if titulo in self.abas:
            p = self.abas[titulo]
            self.batch([
                {"updateCells": {"range": {"sheetId": p["sheetId"]}, "fields": "userEnteredValue,userEnteredFormat"}},
                {"updateSheetProperties": {"properties": {"sheetId": p["sheetId"], "index": indice,
                 "gridProperties": {"rowCount": max(linhas, 50), "columnCount": max(colunas, 10), "frozenRowCount": 0}},
                 "fields": "index,gridProperties"}}])
        else:
            self.batch([{"addSheet": {"properties": {"title": titulo, "index": indice,
                         "gridProperties": {"rowCount": max(linhas, 50), "columnCount": max(colunas, 10)}}}}])
        return self.abas[titulo]["sheetId"]

    def escreve(self, titulo, valores, inicio="A1"):
        for i in range(0, len(valores), 5000):
            r = requests.put(f"{self.base}/values/'{titulo}'!{_desloca(inicio, i)}", headers=self.h,
                             params={"valueInputOption": "USER_ENTERED"}, json={"values": valores[i:i + 5000]})
            if not r.ok:
                raise SystemExit(f"Sheets values ({titulo}): {r.status_code} {r.text[:500]}")

    def formata(self, sid_aba, r0, r1, c0, c1, tipo=None, negrito=False, fundo=None):
        cel, campos = {}, []
        if tipo:
            padrao = {"brl": ("CURRENCY", '"R$" #,##0.00'), "pct": ("PERCENT", "0.00%"), "int": ("NUMBER", "#,##0"),
                      "dec": ("NUMBER", "#,##0.00"), "data": ("DATE", "dd/mm/yyyy"), "x": ("NUMBER", "0.00\"x\"")}[tipo]
            cel["numberFormat"] = {"type": padrao[0], "pattern": padrao[1]}
            campos.append("userEnteredFormat.numberFormat")
        if negrito:
            cel["textFormat"] = {"bold": True}
            campos.append("userEnteredFormat.textFormat.bold")
        if fundo:
            cel["backgroundColor"] = fundo
            campos.append("userEnteredFormat.backgroundColor")
        self.fmt.append({"repeatCell": {"range": {"sheetId": sid_aba, "startRowIndex": r0, "endRowIndex": r1,
                         "startColumnIndex": c0, "endColumnIndex": c1}, "cell": {"userEnteredFormat": cel},
                         "fields": ",".join(campos)}})

    def congela(self, sid_aba, linhas):
        self.fmt.append({"updateSheetProperties": {"properties": {"sheetId": sid_aba,
                         "gridProperties": {"frozenRowCount": linhas}}, "fields": "gridProperties.frozenRowCount"}})

    def larguras(self, sid_aba, colunas, px):
        self.fmt.append({"updateDimensionProperties": {"range": {"sheetId": sid_aba, "dimension": "COLUMNS",
                         "startIndex": colunas[0], "endIndex": colunas[1]}, "properties": {"pixelSize": px},
                         "fields": "pixelSize"}})

    def aplica_formatos(self):
        for i in range(0, len(self.fmt), 400):
            self.batch(self.fmt[i:i + 400])
        self.fmt = []

    def apaga_exceto(self, manter):
        self.batch([{"deleteSheet": {"sheetId": p["sheetId"]}} for t, p in self.abas.items() if t not in manter])


def col(n: int) -> str:  # 0 -> A
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _desloca(inicio, linhas):
    m = re.match(r"([A-Z]+)(\d+)", inicio)
    return f"{m.group(1)}{int(m.group(2)) + linhas}"


CINZA = {"red": 0.93, "green": 0.93, "blue": 0.93}
AZUL = {"red": 0.85, "green": 0.91, "blue": 0.98}
COLS_EXTR = {"dia": "A", "codigo": "D", "expert": "E", "etapa": "F", "publico": "G", "grupo": "M"}


def soma(aba, coluna, **cond):
    """SUMIFS na extração; valor de cond é literal (vira "texto") ou referência de célula (começa com $ ou é A1)."""
    partes = [f"'{aba}'!${coluna}:${coluna}"]
    for k, v in cond.items():
        if v is None or v == "*":
            continue
        c = COLS_EXTR[k]
        ref = v if isinstance(v, str) and v.startswith("@") else None
        partes += [f"'{aba}'!${c}:${c}", ref[1:] if ref else f'"{v}"']
    return f"SUMIFS({'; '.join(partes)})"


def ambas(coluna, **cond):
    return f"{soma(BM, coluna, **cond)} + {soma(GA, coluna, **cond)}"


# ---------------------------------------------------------------- extração

CAB_BM = ["Dia", "Campanha", "Anúncio", "Código", "Expert", "Etapa", "Público", "Formato", "Investimento", "Leads",
          "Cliques no link", "Impressões", "Grupo"]
CAB_GA = ["Dia", "Campanha", "Anúncio", "Código", "Expert", "Etapa", "Público", "Formato", "Custo", "Conversões",
          "Cliques", "Impressões", "Grupo"]


def escreve_extracoes(pl, meta, goog, indice):
    for titulo, cab, rows in ((BM, CAB_BM, meta), (GA, CAB_GA, goog)):
        sid = pl.aba(titulo, len(rows) + 5, len(cab), indice)
        indice += 1
        pl.escreve(titulo, [cab] + rows)
        pl.formata(sid, 0, 1, 0, len(cab), negrito=True, fundo=CINZA)
        pl.formata(sid, 1, len(rows) + 1, 0, 1, "data")
        pl.formata(sid, 1, len(rows) + 1, 8, 9, "brl")
        pl.congela(sid, 1)
    return indice


# ---------------------------------------------------------------- Verba Diária

def faixa(rows_m, rows_g, etapa):
    ds = [r[0] for r in rows_m + rows_g if r[5] == etapa and (r[8] or 0) > 0]
    return (min(ds), max(ds)) if ds else None


def aba_verba(pl, titulo, expert, faixas, indice):
    ex = None if expert == "GERAL" else expert
    v, fmts = [], []  # fmts: (linha0, linha1, col0, col1, tipo)
    neg = []
    v.append([f"VERBA - {L} - {expert}"])
    v.append([])
    v.append(["Etapa", "Previsto", "Investido", "% do previsto", "Diferença", "Facebook previsto", "Facebook investido",
              "Google previsto", "Google investido"])
    neg.append(2)
    l0 = len(v)
    for et in ETAPAS:
        if ex:
            pfb, pga = PLANO[(et, ex)]
        else:
            pfb = sum(PLANO[(et, e)][0] for e in EXPERTS)
            pga = sum(PLANO[(et, e)][1] for e in EXPERTS)
        r = len(v) + 1
        v.append([et, f"=F{r}+H{r}", f"=G{r}+I{r}", f"=IFERROR(C{r}/B{r}; 0)", f"=C{r}-B{r}", pfb,
                  f"={soma(BM, 'I', expert=ex, etapa=et)}", pga, f"={soma(GA, 'I', expert=ex, etapa=et)}"])
    r1 = len(v)
    if not ex:
        v.append(["WhatsApp (disparo)", WHATSAPP, "não medido", "", "", "", "", "", ""])
        v.append(["Reserva", RESERVA, "", "", "", "", "", "", ""])
    t = len(v) + 1
    v.append(["TOTAL", f"=SUM(B{l0 + 1}:B{t - 1})", f"=SUM(C{l0 + 1}:C{r1})", f"=IFERROR(C{t}/B{t}; 0)", f"=C{t}-B{t}",
              f"=SUM(F{l0 + 1}:F{r1})", f"=SUM(G{l0 + 1}:G{r1})", f"=SUM(H{l0 + 1}:H{r1})", f"=SUM(I{l0 + 1}:I{r1})"])
    neg.append(t - 1)
    fmts += [(l0, t, 1, 3, "brl"), (l0, t, 3, 4, "pct"), (l0, t, 4, 9, "brl")]

    v.append([])
    v.append(["INVESTIDO POR PÚBLICO"])
    neg.append(len(v) - 1)
    v.append(["Etapa", "Plataforma", "Aluno", "Super Quente", "Total", "Leads", "CPL"])
    neg.append(len(v) - 1)
    a0 = len(v)
    for et in ETAPAS:
        for plat, aba in PLAT.items():
            r = len(v) + 1
            v.append([et, plat, f"={soma(aba, 'I', expert=ex, etapa=et, publico='Aluno')}",
                      f"={soma(aba, 'I', expert=ex, etapa=et, publico='Super Quente')}",
                      f"={soma(aba, 'I', expert=ex, etapa=et)}", f"={soma(aba, 'J', expert=ex, etapa=et)}",
                      f"=IFERROR(E{r}/F{r}; \"\")"])
    fmts += [(a0, len(v), 2, 5, "brl"), (a0, len(v), 5, 6, "int"), (a0, len(v), 6, 7, "brl")]

    for et in ETAPAS:
        v.append([])
        fx = faixas.get(et)
        if not fx:
            v.append([f"{et.upper()} - POR DIA", f"Sem campanha com a etapa no nome ({L}) no banco."])
            neg.append(len(v) - 1)
            continue
        dias = list(range(fx[0], fx[1] + 1))
        v.append([f"{et.upper()} - POR DIA"])
        neg.append(len(v) - 1)
        hdr = len(v) + 1
        v.append(["", "Total"] + dias)
        neg.append(len(v) - 1)
        fmts.append((hdr - 1, hdr, 2, 2 + len(dias), "data"))
        b0 = len(v)
        linhas_plat = []
        if et == "Captação":
            idx = {"GERAL": 0, "Mateus": 1, "Ivan": 2, "Felipe": 3}[expert]
            prev = [CURVA_DIA.get(dt.date(1899, 12, 30) + dt.timedelta(days=d), (0, 0, 0, 0))[idx] for d in dias]
            r = len(v) + 1
            v.append(["Previsto (curva do plano)", f"=SUM(C{r}:{col(1 + len(dias))}{r})"] + prev)
            linha_prev = r
        r_inv = len(v) + 1
        v.append(["Investido", f"=SUM(C{r_inv}:{col(1 + len(dias))}{r_inv})"] +
                  [f"=SUM({col(2 + i)}{r_inv + 1}:{col(2 + i)}{r_inv + 4})" for i in range(len(dias))])
        for plat, aba in PLAT.items():
            for pub in PUBLICOS:
                r = len(v) + 1
                linhas_plat.append(r)
                v.append([f"{'FB' if plat == 'Facebook' else 'YT'} {pub}", f"=SUM(C{r}:{col(1 + len(dias))}{r})"] +
                         [f"={soma(aba, 'I', expert=ex, etapa=et, publico=pub, dia='@' + col(2 + i) + '$' + str(hdr))}"
                          for i in range(len(dias))])
        r_le = len(v) + 1
        v.append(["Leads", f"=SUM(C{r_le}:{col(1 + len(dias))}{r_le})"] +
                 [f"={ambas('J', expert=ex, etapa=et, dia='@' + col(2 + i) + '$' + str(hdr))}" for i in range(len(dias))])
        v.append(["CPL"] + [f"=IFERROR({col(1 + i)}{r_inv}/{col(1 + i)}{r_le}; \"\")" for i in range(len(dias) + 1)])
        if et == "Captação":
            r = len(v) + 1
            v.append(["Investido − previsto"] + [f"={col(1 + i)}{r_inv}-{col(1 + i)}{linha_prev}" for i in range(len(dias) + 1)])
        fmts += [(b0, len(v), 1, 2 + len(dias), "brl"), (r_le - 1, r_le, 1, 2 + len(dias), "int")]
        neg.append(r_inv - 1)

    largura = max(len(x) for x in v)
    sid = pl.aba(titulo, len(v) + 5, largura + 1, indice)
    pl.escreve(titulo, v)
    pl.formata(sid, 0, 1, 0, 1, negrito=True)
    for n in neg:
        pl.formata(sid, n, n + 1, 0, largura, negrito=True, fundo=CINZA)
    for a, b, c0, c1, tp in fmts:
        pl.formata(sid, a, b, c0, c1, tp)
    pl.larguras(sid, (0, 1), 200)
    return len(v)


# ---------------------------------------------------------------- Captação

def aba_captacao(pl, titulo, expert, faixas, indice):
    ex = None if expert == "GERAL" else expert
    fx = faixas["Captação"]
    dias = list(range(fx[0], fx[1] + 1))
    v = [[f"CAPTAÇÃO - {L} - {expert}", "", "GERAL", "", "", "", "FACEBOOK", "", "", "", "YOUTUBE"]]
    n = len(dias)
    v.append(["", "Total", "=SUM(C4:C%d)" % (3 + n), "=IFERROR(E2/C2; 0)", "=SUM(E4:E%d)" % (3 + n), "",
              "=SUM(G4:G%d)" % (3 + n), "=IFERROR(I2/G2; 0)", "=SUM(I4:I%d)" % (3 + n), "",
              "=SUM(K4:K%d)" % (3 + n), "=IFERROR(M2/K2; 0)", "=SUM(M4:M%d)" % (3 + n)])
    v.append(["Dia da semana", "Data", "Leads", "CPL", "Valor gasto", "", "Leads", "CPL", "Valor gasto", "", "Leads", "CPL",
              "Valor gasto"])
    for i, d in enumerate(dias):
        r = 4 + i
        data = dt.date(1899, 12, 30) + dt.timedelta(days=d)
        v.append([SEMANA[data.weekday()], d, f"=G{r}+K{r}", f"=IFERROR(E{r}/C{r}; 0)", f"=I{r}+M{r}", "",
                  f"={soma(BM, 'J', expert=ex, etapa='Captação', dia=f'@$B{r}')}", f"=IFERROR(I{r}/G{r}; 0)",
                  f"={soma(BM, 'I', expert=ex, etapa='Captação', dia=f'@$B{r}')}", "",
                  f"={soma(GA, 'J', expert=ex, etapa='Captação', dia=f'@$B{r}')}", f"=IFERROR(M{r}/K{r}; 0)",
                  f"={soma(GA, 'I', expert=ex, etapa='Captação', dia=f'@$B{r}')}"])
    fim_dias = len(v)

    blocos = []
    for et, rotulo in (("Captação", "CAPTAÇÃO BLACK - LEADS POR PÚBLICO"), ("Base Forte", "BASE FORTE - LEADS POR PÚBLICO")):
        v.append([])
        v.append(["", "", rotulo])
        v.append(["", "", "Público", "", "Leads", "", "Investimento", "% investimento", "CPL", "", "% leads"])
        b0 = len(v) + 1
        for plat, aba in PLAT.items():
            for pub in PUBLICOS:
                r = len(v) + 1
                v.append(["", "", f"{plat if plat == 'Facebook' else 'YouTube'} {pub}", "",
                          f"={soma(aba, 'J', expert=ex, etapa=et, publico=pub)}", "",
                          f"={soma(aba, 'I', expert=ex, etapa=et, publico=pub)}", f"=IFERROR(G{r}/G{b0 + 4}; 0)",
                          f"=IFERROR(G{r}/E{r}; 0)", "", f"=IFERROR(E{r}/E{b0 + 4}; 0)"])
        r = len(v) + 1
        v.append(["", "", "Total", "", f"=SUM(E{b0}:E{r - 1})", "", f"=SUM(G{b0}:G{r - 1})", f"=SUM(H{b0}:H{r - 1})",
                  f"=IFERROR(G{r}/E{r}; 0)", "", f"=SUM(K{b0}:K{r - 1})"])
        blocos.append((b0, r))
    v.append([])
    v.append(["", "", "AQUECIMENTO", "Valor gasto"])
    ra = len(v) + 1
    v.append(["", "", "Aquecimento FB", f"={soma(BM, 'I', expert=ex, etapa='Aquecimento')}"])
    v.append(["", "", "Aquecimento YT", f"={soma(GA, 'I', expert=ex, etapa='Aquecimento')}"])
    v.append([])
    v.append(["", "", "Total gasto (aquecimento + base forte + captação)", "", "Total de leads (base forte + captação)",
              "", "", "", "CPL geral"])
    rt = len(v) + 1
    (c0, c1), (f0, f1) = blocos
    v.append(["", "", f"=E2+G{f1}+D{ra}+D{ra + 1}", "", f"=C2+E{f1}", "", "", "", f"=IFERROR(C{rt}/E{rt}; 0)"])

    sid = pl.aba(titulo, len(v) + 5, 14, indice)
    pl.escreve(titulo, v)
    for r in (0, 2):
        pl.formata(sid, r, r + 1, 0, 13, negrito=True, fundo=CINZA)
    pl.formata(sid, 1, 2, 0, 13, negrito=True)
    pl.formata(sid, 3, fim_dias, 1, 2, "data")
    for c in (2, 6, 10):
        pl.formata(sid, 1, fim_dias, c, c + 1, "int")
    for c in (3, 4, 7, 8, 11, 12):
        pl.formata(sid, 1, fim_dias, c, c + 1, "brl")
    for b0, r in blocos:
        pl.formata(sid, b0 - 3, b0 - 1, 0, 13, negrito=True, fundo=CINZA)
        pl.formata(sid, b0 - 1, r, 4, 5, "int")
        pl.formata(sid, b0 - 1, r, 6, 7, "brl")
        pl.formata(sid, b0 - 1, r, 7, 8, "pct")
        pl.formata(sid, b0 - 1, r, 8, 9, "brl")
        pl.formata(sid, b0 - 1, r, 10, 11, "pct")
        pl.formata(sid, r - 1, r, 0, 13, negrito=True)
    pl.formata(sid, ra - 2, ra - 1, 0, 13, negrito=True, fundo=CINZA)
    pl.formata(sid, ra - 1, ra + 1, 3, 4, "brl")
    pl.formata(sid, rt - 2, rt - 1, 0, 13, negrito=True, fundo=CINZA)
    pl.formata(sid, rt - 1, rt, 2, 3, "brl")
    pl.formata(sid, rt - 1, rt, 4, 5, "int")
    pl.formata(sid, rt - 1, rt, 8, 9, "brl")
    pl.congela(sid, 3)
    pl.larguras(sid, (0, 1), 130)


def abas_grupos(pl, grupos, indice):
    """Tabela BV_26 (grupos de WhatsApp da Black): uma linha por pessoa × grupo, com a data de entrada."""
    def data(s):
        try:
            return serial(dt.datetime.strptime(str(s).strip()[:10], "%d/%m/%Y").date())
        except ValueError:
            return str(s)
    linhas = [[data(d), g, str(n), int(a or 0)] for d, g, n, a in grupos]
    t1 = "Grupos - Entradas"
    sid = pl.aba(t1, len(linhas) + 5, 4, indice)
    pl.escreve(t1, [["Data de entrada", "Grupo", "Número", "Ainda no grupo (1 = sim)"]] + linhas)
    pl.formata(sid, 0, 1, 0, 4, negrito=True, fundo=CINZA)
    pl.formata(sid, 1, len(linhas) + 1, 0, 1, "data")
    pl.congela(sid, 1)

    por_dia = defaultdict(lambda: [0, 0, set()])
    for d, g, n, a in linhas:
        if isinstance(d, int):
            por_dia[d][0] += 1
            por_dia[d][1] += a
            por_dia[d][2].add(g)
    t2 = "Grupos - Por Dia"
    dias = sorted(por_dia)
    v = [["Data", "Entradas", "Ainda no grupo", "Saíram", "Grupos com entrada no dia", "Entradas acumuladas"]]
    for i, d in enumerate(dias):
        e, a, gs = por_dia[d]
        v.append([d, e, a, e - a, len(gs), f"=SUM($B$2:B{i + 2})"])
    v.append([])
    v.append(["Total", f"=SUM(B2:B{len(dias) + 1})", f"=SUM(C2:C{len(dias) + 1})", f"=SUM(D2:D{len(dias) + 1})"])
    v.append(["Fonte: tabela BV_26 do banco (grupos da Black). \"Saíram\" = entrou naquele dia e hoje não está mais em grupo "
              "nenhum; o banco não guarda a data da saída."])
    sid = pl.aba(t2, len(v) + 5, 6, indice + 1)
    pl.escreve(t2, v)
    pl.formata(sid, 0, 1, 0, 6, negrito=True, fundo=CINZA)
    pl.formata(sid, 1, len(dias) + 1, 0, 1, "data")
    pl.formata(sid, len(dias) + 2, len(dias) + 3, 0, 6, negrito=True)
    pl.congela(sid, 1)


# ---------------------------------------------------------------- Anúncios

def aba_anuncios(pl, titulo, expert, plataforma, meta, goog, indice):
    ex = None if expert == "GERAL" else expert
    gasto = defaultdict(float)
    nome_gasto = defaultdict(float)
    for plat, rows in (("Facebook", meta), ("Google", goog)):
        if plataforma and plat != plataforma:
            continue
        for r in rows:
            if r[12] != "Cadastro" or (ex and r[4] != ex):
                continue
            gasto[r[3]] += r[8]
            nome_gasto[(r[3], r[2])] += r[8]
    nome = {}
    for (cod, ad), g in sorted(nome_gasto.items(), key=lambda x: x[1]):
        nome[cod] = ad  # fica o nome de anúncio com mais gasto
    cods = [c for c, g in sorted(gasto.items(), key=lambda x: -x[1]) if g > 0]
    exv = f'"{ex}"' if ex else '"*"'

    def vendas(r, plat):
        return f"SUMIFS(VENDAS!$D:$D; VENDAS!$A:$A; $B{r}; VENDAS!$B:$B; {exv}; VENDAS!$C:$C; \"{plat}\")"

    sufixo = {"Facebook": " FB", "Google": " YT", None: ""}[plataforma]
    v = [[f"CONTROLE DE DESEMPENHO DE CRIATIVOS - {L} - {expert}{sufixo}", "", "Ticket médio", "=VENDAS!$G$2", "",
          "Captação Black + Base Forte (anúncios de cadastro). Vendas = comprador cujo cadastro veio com o ADxxx no utm_term."]]
    blocos = [(None, "")] if plataforma is None else []
    blocos += [(p, s) for p, s in (("Facebook", " FB"), ("Google", " YT")) if plataforma in (None, p)]
    cab = ["Anúncio", "Código"]
    for p, s in blocos:
        cab += [f"Investimento{s}", f"Leads{s}", f"CPL{s}", f"Vendas{s}", f"Custo / venda{s}", f"ROAS{s}"]
    v.append(cab)
    for i, c in enumerate(cods):
        r = 3 + i
        linha = [nome[c], c]
        for j, (p, s) in enumerate(blocos):
            c0 = 2 + 6 * j
            I, Le, Ve = col(c0), col(c0 + 1), col(c0 + 3)
            if p is None:
                n = len(blocos) - 1
                inv = "=" + "+".join(f"N({col(2 + 6 * k)}{r})" for k in range(1, n + 1))
                leads = "=" + "+".join(f"N({col(3 + 6 * k)}{r})" for k in range(1, n + 1))
                vend = "=" + "+".join(f"N({col(5 + 6 * k)}{r})" for k in range(1, n + 1))
            else:
                aba = PLAT[p]
                inv = f"={soma(aba, 'I', expert=ex, grupo='Cadastro', codigo=f'@$B{r}')}"
                leads = f"={soma(aba, 'J', expert=ex, grupo='Cadastro', codigo=f'@$B{r}')}"
                vend = f"={vendas(r, p)}"
            linha += [inv, leads, f"=IFERROR({I}{r}/{Le}{r}; \"\")", vend, f"=IFERROR({I}{r}/{Ve}{r}; \"\")",
                      f"=IFERROR($D$1*{Ve}{r}/{I}{r}; \"\")"]
        v.append(linha)
    r = len(v) + 1
    tot = ["TOTAL", ""]
    for j in range(len(blocos)):
        c0 = 2 + 6 * j
        I, Le, Ve = col(c0), col(c0 + 1), col(c0 + 3)
        tot += [f"=SUM({I}3:{I}{r - 1})", f"=SUM({Le}3:{Le}{r - 1})", f"=IFERROR({I}{r}/{Le}{r}; \"\")",
                f"=SUM({Ve}3:{Ve}{r - 1})", f"=IFERROR({I}{r}/{Ve}{r}; \"\")", f"=IFERROR($D$1*{Ve}{r}/{I}{r}; \"\")"]
    v.append(tot)
    largura = len(cab)
    sid = pl.aba(titulo, len(v) + 5, largura + 2, indice)
    pl.escreve(titulo, v)
    pl.formata(sid, 0, 1, 0, largura, negrito=True)
    pl.formata(sid, 0, 1, 3, 4, "brl")
    pl.formata(sid, 1, 2, 0, largura, negrito=True, fundo=CINZA)
    pl.formata(sid, len(v) - 1, len(v), 0, largura, negrito=True, fundo=AZUL)
    for j in range(len(blocos)):
        c0 = 2 + 6 * j
        pl.formata(sid, 2, len(v), c0, c0 + 1, "brl")
        pl.formata(sid, 2, len(v), c0 + 1, c0 + 2, "int")
        pl.formata(sid, 2, len(v), c0 + 2, c0 + 3, "brl")
        pl.formata(sid, 2, len(v), c0 + 3, c0 + 4, "int")
        pl.formata(sid, 2, len(v), c0 + 4, c0 + 5, "brl")
        pl.formata(sid, 2, len(v), c0 + 5, c0 + 6, "x")
    pl.congela(sid, 2)
    pl.larguras(sid, (0, 1), 320)
    return len(cods)


def aba_vendas(pl, vendas_rows, ticket, vendas, indice):
    linhas = vendas_rows or [["", "", "", 0]]
    v = [["Código", "Expert", "Plataforma", "Vendas", "", "Total de vendas do lançamento", "Ticket médio"],
         linhas[0] + ["", vendas.total_vendas, ticket]] + linhas[1:]
    v.append([])
    v.append(["Atribuídas a um anúncio", f"=SUM(D2:D{len(linhas) + 1})"])
    v.append(["Fonte: read_vendas (Hotmart + TMB) × lead_utm_lancamento (utm_term/utm_content com ADxxx). Expert pela tag da "
              "campanha do cadastro; sem tag, pelo prefixo do código (MA/IV/FE). Venda sem ADxxx no cadastro não entra aqui."])
    sid = pl.aba("VENDAS", len(v) + 5, 8, indice)
    pl.escreve("VENDAS", v)
    pl.formata(sid, 0, 1, 0, 7, negrito=True, fundo=CINZA)
    pl.formata(sid, 1, 2, 6, 7, "brl")
    pl.congela(sid, 1)


# ---------------------------------------------------------------- principal

def main():
    meta, goog, vendas_rows, ticket, vendas, grupos = carrega()
    faixas = {et: faixa(meta, goog, et) for et in ETAPAS}
    gm = sum(r[8] for r in meta)
    gg = sum(r[8] for r in goog)
    print(f"Banco: Meta {len(meta)} linhas R$ {gm:,.2f} · Google {len(goog)} linhas R$ {gg:,.2f}")
    for et in ETAPAS + ["Outros"]:
        print(f"  {et:12} Meta R$ {sum(r[8] for r in meta if r[5] == et):>10,.2f} · Google R$ "
              f"{sum(r[8] for r in goog if r[5] == et):>10,.2f} · dias {faixas.get(et)}")
    sem = {r[1] for r in meta + goog if r[4] == "Sem expert" or r[5] == "Outros"}
    print(f"  campanhas sem expert ou etapa: {len(sem)}", *sorted(sem)[:10], sep="\n    ")
    print(f"Vendas: {vendas.total_vendas} · ticket {ticket} · atribuídas a anúncio {sum(r[3] for r in vendas_rows)}")
    print(f"Grupos BV_26: {len(grupos)} linhas")
    if not APPLY:
        print("Simulação. Rode com --apply para gravar.")
        return

    # Verba Diária
    # as abas que as fórmulas citam têm de existir antes: fórmula gravada com aba inexistente fica em erro para sempre
    pl = Planilha(PLANILHAS["verba"])
    escreve_extracoes(pl, meta, goog, 0)
    for i, ex in enumerate(["GERAL"] + EXPERTS):
        aba_verba(pl, f"Verba Diária [{L}] - {ex}", ex, faixas, i)
    pl.aplica_formatos()
    pl.apaga_exceto({f"Verba Diária [{L}] - {e}" for e in ["GERAL"] + EXPERTS} | {BM, GA})
    print("Verba Diária ok")

    # Captação
    pl = Planilha(PLANILHAS["captacao"])
    escreve_extracoes(pl, meta, goog, 0)
    for i, ex in enumerate(["GERAL"] + EXPERTS):
        aba_captacao(pl, f"Captação [{L}] - {ex}", ex, faixas, i)
    abas_grupos(pl, grupos, len(EXPERTS) + 1)
    pl.aplica_formatos()
    pl.apaga_exceto({f"Captação [{L}] - {e}" for e in ["GERAL"] + EXPERTS} |
                    {"Grupos - Entradas", "Grupos - Por Dia", BM, GA})
    print("Captação ok")

    # Anúncios
    pl = Planilha(PLANILHAS["anuncios"])
    escreve_extracoes(pl, meta, goog, 0)
    aba_vendas(pl, vendas_rows, ticket, vendas, 0)
    manter, i = set(), 0
    for ex in ["GERAL"] + EXPERTS:
        nome = "Geral" if ex == "GERAL" else ex
        for plat, suf in ((None, ""), ("Facebook", " FB"), ("Google", " YT")):
            t = f"Anúncios - {nome}{suf} [{L}]"
            n = aba_anuncios(pl, t, ex, plat, meta, goog, i)
            print(f"  {t}: {n} anúncios")
            manter.add(t)
            i += 1
    pl.aplica_formatos()
    pl.apaga_exceto(manter | {"VENDAS", BM, GA})
    print("Anúncios ok")


if __name__ == "__main__":
    main()
