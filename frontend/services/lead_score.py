"""
frontend/services/lead_score.py — Qualidade dos leads pelo score da pesquisa (bloco do debriefing).

O modelo (regressão logística treinada em lançamentos fechados) vem pronto de `config/lead_score_modelo.json`,
gerado por `scripts/lead_score_treino.py --exportar`. Aqui só se aplica: quem respondeu a pesquisa recebe uma
probabilidade de compra pelas respostas; quem não respondeu é a faixa C. Faixas:
  A — respondeu e a probabilidade fica na metade de cima dos respondentes DO LANÇAMENTO;
  B — respondeu, metade de baixo;
  C — não respondeu a pesquisa.
Só lê. Cobre lançamentos cuja pesquisa está no sistema novo (perguntas com título); o Typeform antigo (ids de
campo) devolve None e o bloco some.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from frontend.db import _get_engine
from logger import get_logger

logger = get_logger("lead_score")

_MODELO_JSON = Path(__file__).resolve().parent.parent.parent / "config" / "lead_score_modelo.json"
_modelo: dict | None = None

# Mesmos padrões de `scripts/lead_score_dataset.py` (texto da pergunta normalizado, sem acento).
_PADROES = {
    "idade": r"\bidade\b",
    "genero": r"\bgenero\b",
    "estado": r"qual estado|de qual estado",
    "filhos": r"quantos filhos",
    "mora": r"com quem voce mora",
    "escolaridade": r"escolaridade",
    "situacao": r"situacao profissional",
    "nivel": r"voce se considera",
}
_PAD_PREOCUP = r"selecione as \d opcoes"        # múltipla escolha: "3 opções que mais preocupam você"


def _norm(s: Any) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


def _limpa(v: Any) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip().lower()[:60]


def _carregar_modelo() -> dict | None:
    global _modelo
    if _modelo is None:
        try:
            _modelo = json.loads(_MODELO_JSON.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("lead_score: modelo ausente em %s", _MODELO_JSON)
            return None
    return _modelo


def _probabilidades(m: dict, resp: pd.DataFrame) -> list[float]:
    """Mesma codificação do treino: `respondeu`=1 + uma coluna por (pergunta, resposta conhecida)."""
    nomes_cols: list[tuple[str, str]] = [(q, v) for q in m["perguntas"] for v in m["vocab"][q]]
    coef = m["coef"]
    peso = {nc: coef[i + 1] for i, nc in enumerate(nomes_cols)}
    base = m["intercepto"] + coef[0]
    # Múltipla escolha (preocupações): uma coluna 0/1 por opção, depois das de escolha única (mesma ordem do treino).
    opcoes = (m.get("multi") or {}).get("preocup") or []
    peso_op = coef[1 + len(nomes_cols): 1 + len(nomes_cols) + len(opcoes)]
    out = []
    for _, r in resp.iterrows():
        z = base
        for q in m["perguntas"]:
            z += peso.get((q, r[q]), 0.0)
        txt = r.get("preocup") or ""
        for o, w in zip(opcoes, peso_op):
            if o in txt:
                z += w
        out.append(1.0 / (1.0 + math.exp(-z)))
    return out


_AD_SQL = (
    "COALESCE(substring(UPPER(COALESCE(utm_term, '')) FROM '^(AD[0-9]+)'), "
    "substring(UPPER(COALESCE(utm_content, '')) FROM '^(AD[0-9]+)'))"
)
_MIN_LEADS_ANUNCIO = 200
_TOP_ANUNCIOS = 15


def gasto_por_anuncio(meta: Any, google: Any) -> dict[str, dict]:
    """{ADxxx: {nome, gasto}} somando Meta + Google (mesmas listas do perfil por anúncio do debriefing)."""
    info: dict[str, dict] = {}
    for a in [
        *(getattr(meta, "preq_por_ad", None) or []), *(getattr(meta, "captacao_por_ad", None) or []),
        *(getattr(google, "preq_por_ad", None) or []), *(getattr(google, "anuncios_por_ad", None) or []),
    ]:
        cod = str(a.get("ad_code") or "").upper()
        if cod:
            d = info.setdefault(cod, {"nome": a.get("nome") or cod, "gasto": 0.0})
            d["gasto"] += float(a.get("gasto") or 0)
    return info


def _respostas_df(code: str, m: dict) -> pd.DataFrame | None:
    """Respostas da pesquisa do sistema novo: uma linha por e-mail, colunas = as perguntas do modelo + `preocup`
    (texto normalizado da múltipla escolha). None se o lançamento não tem pesquisa pontuável."""
    from frontend.db_readers.typeform import _novo_sistema_respostas_cached  # noqa: PLC0415

    tf = _novo_sistema_respostas_cached(code)
    if tf is None or tf.empty:
        return None
    cols = {}
    for q, pad in _PADROES.items():
        col = next((c for c in tf.columns if c != "email_norm" and re.search(pad, _norm(c))), None)
        if col:
            cols[q] = col
    if len(cols) < 4:                       # pesquisa sem as perguntas-padrão: não dá para pontuar
        return None
    tf = tf.drop_duplicates("email_norm", keep="last")
    resp = pd.DataFrame({"email": tf["email_norm"].values})
    for q in m["perguntas"]:
        resp[q] = tf[cols[q]].map(_limpa).values if q in cols else ""
    col_pre = next((c for c in tf.columns if c != "email_norm" and re.search(_PAD_PREOCUP, _norm(c))), None)
    resp["preocup"] = tf[col_pre].map(_norm).values if col_pre else ""
    return resp


def calcular(code: str, emails_compradores: set[str], anuncios: dict[str, dict] | None = None) -> dict | None:
    """{faixas:[{faixa,leads,pct_leads,compradores,taxa,pct_compradores}], total_leads, respondentes, ...} ou None."""
    m = _carregar_modelo()
    if not m:
        return None
    resp = _respostas_df(code, m)
    if resp is None:
        return None

    emails = [e for e in resp["email"].tolist() if e]
    compradores = sorted(emails_compradores or [])
    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        no_lead = {r[0] for r in conn.execute(
            text("SELECT DISTINCT email FROM lead_utm_lancamento WHERE lancamento_codigo = :c AND email = ANY(:e)"),
            {"c": code, "e": emails})}
        total_leads = int(conn.execute(
            text("SELECT COUNT(DISTINCT email) FROM lead_utm_lancamento WHERE lancamento_codigo = :c AND email <> ''"),
            {"c": code}).scalar() or 0)
        compradores_nos_leads = {r[0] for r in conn.execute(
            text("SELECT DISTINCT email FROM lead_utm_lancamento WHERE lancamento_codigo = :c AND email = ANY(:e)"),
            {"c": code, "e": compradores})} if compradores else set()
    resp = resp[resp["email"].isin(no_lead)].reset_index(drop=True)
    if resp.empty or total_leads <= 0:
        return None

    resp["p"] = _probabilidades(m, resp)
    # Corte relativo ao lançamento: o modelo não separa por produto (a taxa de compra do PES é o dobro da do PI),
    # então um limiar fixo põe quase todos os respondentes de um produto na mesma faixa.
    limiar = float(resp["p"].median())
    resp["faixa"] = ["A" if p > limiar else "B" for p in resp["p"]]
    resp["comprou"] = resp["email"].isin(compradores_nos_leads)

    # Anúncio de origem (ADxxx do utm_term/utm_content) do lead: total por anúncio, dos respondentes e dos compradores.
    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 120000"))
        leads_por_ad = {r[0]: int(r[1]) for r in conn.execute(text(
            "SELECT " + _AD_SQL + " AS ad, COUNT(DISTINCT email) FROM lead_utm_lancamento "
            "WHERE lancamento_codigo = :c AND " + _AD_SQL + " IS NOT NULL GROUP BY 1"), {"c": code})}
        ad_de: dict[str, str] = {}
        for lote in (resp["email"].tolist(), sorted(compradores_nos_leads)):
            if not lote:
                continue
            for e, ad in conn.execute(text(
                    "SELECT email, " + _AD_SQL + " FROM lead_utm_lancamento "
                    "WHERE lancamento_codigo = :c AND email = ANY(:e) AND " + _AD_SQL + " IS NOT NULL"),
                    {"c": code, "e": lote}):
                ad_de.setdefault(e, ad)
    resp["ad"] = resp["email"].map(ad_de)
    por_ad: dict[str, dict] = {
        ad: {"ad": ad, "leads": n, "resp": 0, "a": 0, "b": 0, "compradores": 0} for ad, n in leads_por_ad.items()}
    for ad, faixa in zip(resp["ad"], resp["faixa"]):
        if ad in por_ad:
            por_ad[ad]["resp"] += 1
            por_ad[ad]["a" if faixa == "A" else "b"] += 1
    for e in compradores_nos_leads:
        ad = ad_de.get(e)
        if ad in por_ad:
            por_ad[ad]["compradores"] += 1
    anuncios = anuncios or {}
    linhas_ad = []
    for ad, d in por_ad.items():
        if d["leads"] < _MIN_LEADS_ANUNCIO:
            continue
        gasto = float((anuncios.get(ad) or {}).get("gasto") or 0)
        d.update({
            "nome": (anuncios.get(ad) or {}).get("nome") or ad, "gasto": gasto,
            "pct_resp": d["resp"] / d["leads"] * 100,
            "pct_a_resp": d["a"] / d["resp"] * 100 if d["resp"] else 0.0,
            "cpl": gasto / d["leads"] if gasto else 0.0,
            "custo_a": gasto / d["a"] if gasto and d["a"] else 0.0,
            "cpa": gasto / d["compradores"] if gasto and d["compradores"] else 0.0,
        })
        linhas_ad.append(d)
    linhas_ad.sort(key=lambda d: d["gasto"], reverse=True)

    n_resp = len(resp)
    compr_total = len(compradores_nos_leads)
    linhas = []
    for faixa in ("A", "B"):
        sub = resp[resp["faixa"] == faixa]
        linhas.append({"faixa": faixa, "leads": len(sub), "compradores": int(sub["comprou"].sum())})
    linhas.append({"faixa": "C", "leads": total_leads - n_resp,
                   "compradores": compr_total - int(resp["comprou"].sum())})
    for l in linhas:
        l["pct_leads"] = l["leads"] / total_leads * 100 if total_leads else 0.0
        l["taxa"] = l["compradores"] / l["leads"] * 100 if l["leads"] else 0.0
        l["pct_compradores"] = l["compradores"] / compr_total * 100 if compr_total else 0.0
    return {
        "faixas": linhas, "total_leads": total_leads, "respondentes": n_resp,
        "pct_respondentes": n_resp / total_leads * 100, "compradores": compr_total,
        "taxa_geral": compr_total / total_leads * 100 if total_leads else 0.0,
        "anuncios": linhas_ad[:_TOP_ANUNCIOS],
        "auc_resp": m.get("auc_medio_entre_respondentes"), "lancamentos_treino": len(m.get("lancamentos") or []),
    }


def obter(code: str, emails_compradores: set[str], anuncios: dict[str, dict] | None = None) -> dict | None:
    """`calcular` com cache de 30 min por lançamento (leva ~15 s: Typeform novo + consultas na base de leads)."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415

    return _get_or_compute(code, "lead_score", lambda: calcular(code, emails_compradores, anuncios), ttl=1800)


# ── Score por lead, com origem (CSV de /leads/score.csv) ──────────────────────────────────────────────────────
# Segundo modelo, à parte do bloco do debriefing: além das respostas, usa a ORIGEM do lead (canal, temperatura e etapa
# da campanha, lidos do UTM). Pontua TAMBÉM quem não respondeu a pesquisa. Fica fora do bloco porque o canal entra no
# score: usar essa nota para julgar anúncios repetiria o canal (ver ARQUITETURA, «Score por lead com origem»).
_MODELO_ORIGEM_JSON = Path(__file__).resolve().parent.parent.parent / "config" / "lead_score_modelo_origem.json"
_modelo_origem: dict | None = None
_TEMPERATURAS = ("super quente", "quente", "morno", "frio", "organico", "aluno")


def _carregar_modelo_origem() -> dict | None:
    global _modelo_origem
    if _modelo_origem is None:
        try:
            _modelo_origem = json.loads(_MODELO_ORIGEM_JSON.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("lead_score: modelo com origem ausente em %s", _MODELO_ORIGEM_JSON)
            return None
    return _modelo_origem


def derivar_origem(utm_source: Any, utm_campaign: Any) -> pd.DataFrame:
    """canal / temp / etapa a partir do UTM — a MESMA regra do treino (`scripts/lead_score_treino_origem.py`).
    canal: google (inclui YouTube) | meta | vazio | outro (nos lançamentos antigos o YouTube vem como `yt-…` e cai aqui);
    temp: quente/frio/… lido de `[quente]` no nome da campanha (só existe nas campanhas de mai/26 em diante);
    etapa: pre (pré-qualificação) | capt (captação) | outro."""
    src = pd.Series(utm_source).fillna("").map(_norm).reset_index(drop=True)
    camp = pd.Series(utm_campaign).fillna("").map(_norm).reset_index(drop=True)
    canal = np.where(src.str.contains("google|youtube|gads"), "google",
                     np.where(src.str.contains("face|fb|meta|insta|ig"), "meta",
                              np.where(src == "", "vazio", "outro")))

    def _temp(c: str) -> str:
        for t in _TEMPERATURAS:
            if f"[{t}]" in c:
                return t
        return "outro"

    etapa = np.where(camp.str.contains("qualifica"), "pre", np.where(camp.str.contains("capta"), "capt", "outro"))
    return pd.DataFrame({"canal": canal, "temp": camp.map(_temp).values, "etapa": etapa})


def _logit_vetorial(m: dict, df: pd.DataFrame, com_origem: bool = False) -> np.ndarray:
    """Probabilidade de compra de cada linha de `df` (colunas: `respondeu` 0/1, as perguntas do modelo, `preocup`,
    e `canal`/`temp`/`etapa` quando `com_origem`). Mesma codificação do treino: respondeu, respostas de escolha
    única, opções de preocupação, [coluna de «linha de carga», sempre 0 aqui] e, por fim, a origem."""
    coef = m["coef"]
    z = np.full(len(df), float(m["intercepto"]))
    z += coef[0] * df["respondeu"].to_numpy(dtype=float)
    i = 1
    for q in m["perguntas"]:
        for v in m["vocab"][q]:
            z += coef[i] * (df[q].to_numpy() == v)
            i += 1
    opcoes = (m.get("multi") or {}).get("preocup") or []
    txt = df["preocup"].fillna("").astype(str)
    for o in opcoes:
        z += coef[i] * txt.str.contains(o, regex=False).to_numpy()
        i += 1
    if com_origem:
        i += int(m.get("colunas_controle", 0))              # controle do tipo de linha: não vale para lead novo
        for campo, valor in m["origem"]["cols"]:
            z += coef[i] * (df[campo].to_numpy() == valor)
            i += 1
    return 1.0 / (1.0 + np.exp(-z))


def calcular_leads(code: str, emails_compradores: set[str]) -> pd.DataFrame | None:
    """Um DataFrame com um lead por linha: e-mail, se respondeu, faixa e nota só pela pesquisa (como o bloco do
    debriefing), canal/temperatura/etapa, nota e decil com origem (vale para todos) e se comprou. None sem modelo/leads."""
    m, mo = _carregar_modelo(), _carregar_modelo_origem()
    if not m or not mo:
        return None
    with _get_engine().connect() as conn:
        conn.execute(text("SET LOCAL statement_timeout = 180000"))
        rows = conn.execute(text(
            "SELECT DISTINCT ON (email) email, utm_source, utm_campaign FROM lead_utm_lancamento "
            "WHERE lancamento_codigo = :c AND email <> '' ORDER BY email, primeiro_visto_em"), {"c": code}).fetchall()
    if not rows:
        return None
    leads = pd.DataFrame(rows, columns=["email", "utm_source", "utm_campaign"])
    leads = pd.concat([leads[["email"]], derivar_origem(leads["utm_source"], leads["utm_campaign"])], axis=1)

    resp = _respostas_df(code, m)
    cols_resp = [*m["perguntas"], "preocup"]
    if resp is not None and not resp.empty:
        leads = leads.merge(resp, on="email", how="left", indicator="_m")
        leads["respondeu"] = (leads.pop("_m") == "both").astype(int)
    else:
        leads["respondeu"] = 0
    for c in cols_resp:
        leads[c] = leads[c].fillna("") if c in leads else ""

    resp_mask = leads["respondeu"].to_numpy() == 1
    leads["p_pesquisa"] = np.nan
    if resp_mask.any():
        p = _logit_vetorial(m, leads[resp_mask])
        leads.loc[resp_mask, "p_pesquisa"] = p
        corte = float(np.median(p))
        leads["faixa_pesquisa"] = np.where(~resp_mask, "C", np.where(leads["p_pesquisa"] > corte, "A", "B"))
        leads["nota_pesquisa"] = (leads["p_pesquisa"].rank(pct=True) * 100).round().astype("Int64")
    else:
        leads["faixa_pesquisa"], leads["nota_pesquisa"] = "C", pd.NA

    leads["p_origem"] = _logit_vetorial(mo, leads, com_origem=True)
    leads["nota_origem"] = (leads["p_origem"].rank(pct=True) * 100).round().astype(int).clip(lower=1)
    # Decil com tamanhos iguais: muitos leads empatam na mesma nota (mesmo canal e campanha, sem pesquisa), e o rank
    # médio deixaria decis vazios. `first` desempata pela ordem da consulta (e-mail), sem efeito na ordenação.
    leads["decil_origem"] = (np.ceil(leads["p_origem"].rank(method="first", pct=True) * 10)).astype(int).clip(1, 10)
    compradores = set(emails_compradores or [])
    leads["comprou"] = leads["email"].isin(compradores)
    leads = leads.sort_values("p_origem", ascending=False).reset_index(drop=True)
    leads.attrs["gerado_em"] = datetime.now().strftime("%d/%m %H:%M")
    return leads


def obter_leads(code: str, emails_compradores: set[str]) -> pd.DataFrame | None:
    """`calcular_leads` com cache de 30 min por lançamento (consulta de até ~300 mil leads)."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415

    return _get_or_compute(code, "lead_score_leads", lambda: calcular_leads(code, emails_compradores), ttl=1800)


def obter_leads_do_lancamento(code: str) -> pd.DataFrame | None:
    """Score por lead do lançamento, com os compradores (Hotmart | TMB) lidos aqui. É o ÚNICO caminho que chama
    `obter_leads` para os consumidores do painel (/leads e /criativos): os dois dividem a entrada de cache
    `lead_score_leads`, então passar um conjunto de compradores diferente (ex.: vazio) envenenaria o outro."""
    from frontend.db_readers.sales import read_vendas  # noqa: PLC0415

    v = read_vendas(code)
    compradores = (v.emails_hotmart | v.emails_tmb) if v else set()
    return obter_leads(code, compradores)


def resumo_painel(df: pd.DataFrame) -> dict:
    """Escada de compra do score com origem (por decil) e da pesquisa (A/B/C) para a /leads, mais um veredito de
    «estamos no caminho certo?»: quanto mais compra os 30% de maior nota (decis 8–10) em relação aos 30% de menor
    (decis 1–3). A leitura só é firme com compradores suficientes; antes disso o veredito diz que ainda é cedo."""
    total, compr = len(df), int(df["comprou"].sum())
    base = compr / total * 100 if total else 0.0
    decis = []
    for k in range(10, 0, -1):
        s = df[df["decil_origem"] == k]
        n, c = len(s), int(s["comprou"].sum())
        taxa = c / n * 100 if n else 0.0
        decis.append({"decil": k, "leads": n, "compradores": c, "taxa": taxa, "lift": taxa / base if base else 0.0})
    topo, fundo = df[df["decil_origem"] >= 8], df[df["decil_origem"] <= 3]
    t_topo = topo["comprou"].mean() * 100 if len(topo) else 0.0
    t_fundo = fundo["comprou"].mean() * 100 if len(fundo) else 0.0
    razao = t_topo / t_fundo if t_fundo > 0 else None
    faixas = []
    for f in ("A", "B", "C"):
        s = df[df["faixa_pesquisa"] == f]
        c = int(s["comprou"].sum())
        faixas.append({"faixa": f, "leads": len(s), "compradores": c, "taxa": c / len(s) * 100 if len(s) else 0.0})
    nr = df[df["respondeu"] == 0]
    mediana = nr["p_origem"].median() if len(nr) else 0.0
    nr_alta, nr_baixa = nr[nr["p_origem"] > mediana], nr[nr["p_origem"] <= mediana]
    if compr == 0:
        estado, texto = "cedo", "Ainda sem compradores neste lançamento: a escada aparece aqui conforme as vendas entram."
    elif compr < _MIN_COMPRADORES_VEREDITO:
        estado, texto = "cedo", (f"Ainda é cedo: {compr} compradores até agora. A tendência já aparece, mas a leitura só fica firme "
                                 f"a partir de ~{_MIN_COMPRADORES_VEREDITO}.")
    elif razao is None or razao >= _RAZAO_BOA:
        estado, texto = "ok", "No caminho: o score está separando quem compra de quem não compra, como nos lançamentos fechados."
    elif razao >= _RAZAO_FRACA:
        estado, texto = "atencao", "Abaixo do esperado: o score ainda separa, mas menos que nos lançamentos fechados."
    else:
        estado, texto = "ruim", "Fora do esperado: os leads de maior nota quase não compram mais que os de menor. Vale investigar."
    return {
        "total": total, "compradores": compr, "base": base, "decis": decis, "faixas": faixas,
        "t_topo": t_topo, "t_fundo": t_fundo, "razao": razao, "estado": estado, "texto": texto,
        "nr_alta": float(nr_alta["comprou"].mean() * 100) if len(nr_alta) else 0.0,
        "nr_baixa": float(nr_baixa["comprou"].mean() * 100) if len(nr_baixa) else 0.0,
        "nr_total": len(nr), "gerado_em": df.attrs.get("gerado_em"),
    }


_MIN_COMPRADORES_VEREDITO = 100
# Razão (taxa dos decis 8–10 ÷ taxa dos decis 1–3) nos 11 lançamentos fechados de 2026: 1,0 · 1,4 · 1,4 · 1,4 · 1,8 · 1,9 · 2,2 ·
# 2,3 · 2,6 · 4,1 · 5,4 (mediana ~2; medida na própria base de treino, então levemente otimista). Limites: «no caminho» a partir de
# 1,7 (7 de 11), «abaixo do esperado» de 1,3 a 1,7 (3 de 11), «fora do esperado» abaixo de 1,3 (1 de 11).
_RAZAO_BOA, _RAZAO_FRACA = 1.7, 1.3
