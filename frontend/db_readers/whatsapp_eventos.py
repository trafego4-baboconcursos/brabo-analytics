"""
frontend/db_readers/whatsapp_eventos.py — Grupos de WhatsApp a partir de `leads_grupos_eventos` (banco analytics).

Desde 22/10/26 a automação grava um EVENTO por entrada/saída de grupo (`ent_sai` = Entrou/Saiu, com hora real)
em `leads_grupos_eventos`, em vez de uma tabela por lançamento (`<COD>_API`) + a planilha do poller. O
`nome_campanha` traz o lançamento entre colchetes: "Projeto INSS [PI-NOV-26]" (grupos normais) e
"Grupo VIP [PI-NOV-26]" (VIP). Ao contrário das tabelas antigas, há data de SAÍDA — dá para ter entradas e saídas
reais por dia.

Usado só como alternativa: lançamento que ainda tem dado no modelo antigo (tabelas `_API` / `whatsapp_sheets_*`)
continua lendo de lá. A Black (BV-26) também fica de fora — os grupos dela têm outra nomenclatura.

Contas (validadas em 27/10/26):
  - pessoa "ativa" = está em pelo menos um grupo cujo ÚLTIMO evento foi Entrou;
  - total = pessoas distintas que já entraram; total limpo = ativas agora;
  - entradas do dia = pessoas cuja PRIMEIRA entrada no bloco foi naquele dia; saídas do dia = pessoas distintas
    com evento Saiu naquele dia; "leads totais" do dia = total limpo ao fim do dia;
  - bate com a tabela antiga em lançamento fechado (PI-AGO-26: 409.919 / 380.537 nos dois) e com a view
    `vw_leads_ativos_grupos` em ~0,2% (a view conta por campanha, aqui por grupo).
  - o dia 22/10/26 é a CARGA INICIAL da automação: concentra o que já estava nos grupos, não é movimento do dia.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text

from logger import get_logger
from frontend.db import _get_engine
from frontend.utils import _extract_launch_code
from src.constants import e_black

logger = get_logger("db")

# O nome da campanha nos grupos nem sempre é o código do lançamento: os grupos do PES-NOV-26 (captação
# pós-edital) saem como "[PES-PPE-26]". Premissa a confirmar com a automação (ver MUDANCAS_PES-NOV-26).
CODIGOS_EVENTOS: dict[str, tuple[str, ...]] = {"PES-NOV-26": ("PES-PPE-26",)}

_FUSO = "America/Sao_Paulo"


def _codigos(code: str) -> list[str]:
    return [code, *CODIGOS_EVENTOS.get(code.upper(), ())]


def _carregar(code: str) -> pd.DataFrame:
    filtros = " OR ".join(f"nome_campanha ILIKE :p{i}" for i, _ in enumerate(_codigos(code)))
    params = {f"p{i}": f"%[{c}]%" for i, c in enumerate(_codigos(code))}
    with _get_engine().connect() as conn:
        return pd.read_sql(
            text(f"""SELECT timestamp, nome_grupo, TRIM(ent_sai) AS ent_sai, numero_lead::text AS numero_lead, nome_campanha
                     FROM leads_grupos_eventos WHERE {filtros}"""),
            conn, params=params,
        )


def _varredura(df: pd.DataFrame) -> dict:
    """Percorre os eventos em ordem e devolve resumo + série diária de um bloco."""
    df = df.assign(dia=df["timestamp"].dt.tz_convert(_FUSO).dt.date).sort_values("timestamp", kind="stable")
    estado: dict[tuple, bool] = {}
    ativos: dict[str, int] = {}
    vistos: set[str] = set()
    limpo = 0
    entradas: dict[date, set] = {}
    saidas: dict[date, set] = {}
    fim: dict[date, int] = {}
    for dia, grupo, ent_sai, numero in zip(df["dia"], df["nome_grupo"], df["ent_sai"], df["numero_lead"]):
        if numero not in vistos:
            vistos.add(numero)
            entradas.setdefault(dia, set()).add(numero)
        entrou = ent_sai == "Entrou"
        if not entrou:
            saidas.setdefault(dia, set()).add(numero)
        chave = (numero, grupo)
        if estado.get(chave, False) != entrou:
            antes = ativos.get(numero, 0)
            depois = antes + (1 if entrou else -1)
            ativos[numero] = depois
            if antes == 0 and depois > 0:
                limpo += 1
            elif antes > 0 and depois == 0:
                limpo -= 1
        estado[chave] = entrou
        fim[dia] = limpo

    # série contínua, um item por dia entre o primeiro e o último com evento (o dia sem evento herda o saldo)
    linhas, corrente = [], 0
    if fim:
        for ts in pd.date_range(min(fim), max(fim), freq="D"):
            d = ts.date()
            corrente = fim.get(d, corrente)
            e, s = len(entradas.get(d, ())), len(saidas.get(d, ()))
            linhas.append({
                "data": d.isoformat(), "data_str": d.strftime("%d/%m/%Y"),
                "entradas": e, "saidas": s, "relacao": e - s, "leads_no_dia": corrente,
            })
    ultimo = linhas[-1] if linhas else {"entradas": 0, "saidas": 0}
    return {
        "resumo": {
            "total": len(vistos), "total_limpo": limpo, "grupos": int(df["nome_grupo"].nunique()),
            "entradas_hoje": ultimo["entradas"], "saidas_hoje": ultimo["saidas"],
            "multi_grupo": sum(1 for v in ativos.values() if v >= 2),
            "entradas": len(vistos), "saidas": len(vistos) - limpo,
        },
        "diario": linhas,
    }


def _picos(diario: list[dict]) -> dict:
    out = {"leads_no_dia": None, "saidas": None}
    for l in diario:
        if out["leads_no_dia"] is None or l["leads_no_dia"] > out["leads_no_dia"]["valor"]:
            out["leads_no_dia"] = {"valor": int(l["leads_no_dia"]), "data": l["data"]}
        if out["saidas"] is None or l["saidas"] > out["saidas"]["valor"]:
            out["saidas"] = {"valor": int(l["saidas"]), "data": l["data"]}
    return out


def _calcular(code: str) -> dict[str, dict]:
    df = _carregar(code)
    if df.empty:
        return {}
    e_vip = df["nome_campanha"].str.contains("VIP", case=False, na=False)
    out: dict[str, dict] = {}
    for bloco, sub in (("normal", df[~e_vip]), ("vip", df[e_vip])):
        if sub.empty:
            continue
        r = _varredura(sub)
        r["pico"] = _picos(r["diario"])
        out[bloco] = r
    return out


def ler(launch_folder_or_code: Any) -> dict[str, dict]:
    """{"normal": {"resumo", "diario", "pico"}, "vip": {...}} — vazio se o lançamento não tem eventos
    (ou é a Black). Cacheado 5 min, como o resto da contagem de grupos."""
    from frontend.cache import _get_or_compute  # noqa: PLC0415 — evita import circular

    code = _extract_launch_code(launch_folder_or_code)
    if not code or e_black(code):
        return {}
    try:
        return _get_or_compute(code, "whatsapp_eventos", lambda: _calcular(code), ttl=300) or {}
    except Exception:
        logger.exception("whatsapp_eventos: falha para %s", code)
        return {}


def resumo_wa(launch_folder_or_code: Any) -> dict | None:
    """Dict no formato de `read_whatsapp_groups` (start/end/normal/vip), para a página /whatsapp."""
    dados = ler(launch_folder_or_code)
    if not dados:
        return None
    datas = [l["data"] for b in dados.values() for l in b["diario"]]
    return {
        "start": min(datas) if datas else "", "end": max(datas) if datas else "",
        "normal": dict(dados["normal"]["resumo"]) if "normal" in dados else None,
        "vip": dict(dados["vip"]["resumo"]) if "vip" in dados else None,
        "overlap_vip": 0, "compradores": None,
    }
