"""
frontend/services/resumo.py — contexto da página /resumo (painel de vendas de uma tela só).

Reaproveita o que o /funil e o /debriefing já calculam (receita, vendas, investimento, vendas por
produto/dia, forma de pagamento) e acrescenta o perfil dos compradores (aluno x novo).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from frontend.db_readers.resumo import read_perfil_compradores
from frontend.utils import _safe_date

_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
          "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


_ABREV = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
          "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
_SUFIXO_OFERTA = re.compile(r"\s*-\s*(?:lead|crossell|cross\s?sell|upsell)\w*\s*$", re.IGNORECASE)
_PROJETO = {"PES": "Escrevente", "PI": "INSS", "PBB": "Banco do Brasil", "BV": "Black Vitalícia"}


def _f(x: Any) -> float:
    return float(x or 0)


def titulo_do_lancamento(code: str) -> str:
    """'PES-SET-26' -> 'Projeto Escrevente de Setembro de 2026 [PES-SET-26]'."""
    partes = str(code or "").upper().split("-")
    if len(partes) >= 3 and partes[1] in _ABREV and partes[2].isdigit():
        projeto = _PROJETO.get(partes[0], partes[0])
        mes = _MESES[_ABREV[partes[1]] - 1].capitalize()
        return f"Projeto {projeto} de {mes} de 20{partes[2]} [{code}]"
    return f"Projeto [{code}]"


def _dias_do_carrinho(cfg: dict, hm: Any, tmb: Any, hoje: date) -> dict:
    """Vendas por dia do carrinho (zero nos dias sem venda), do início até hoje/fim."""
    ini = _safe_date(cfg.get("carrinho_start_date"))
    fim = _safe_date(cfg.get("carrinho_end_date"))
    por_dia: dict[str, int] = {}
    for tl in ((getattr(hm, "timeline", None) or []), (getattr(tmb, "timeline", None) or [])):
        for t in tl:
            k = str(t.get("data") or "")[:10]
            if k:
                por_dia[k] = por_dia.get(k, 0) + int(t.get("vendas") or 0)
    if not ini and por_dia:
        ini = date.fromisoformat(min(por_dia))
    if not ini:
        return {"rotulos": [], "valores": [], "mes": ""}
    ate = min(fim, hoje) if fim else hoje
    if por_dia:
        ate = max(ate, date.fromisoformat(max(por_dia)))
    rotulos, valores, d = [], [], ini
    while d <= ate and (d - ini).days < 120:
        rotulos.append(str(d.day))
        valores.append(por_dia.get(d.isoformat(), 0))
        d += timedelta(days=1)
    mes = _MESES[ini.month - 1] if ini.month == ate.month else f"{_MESES[ini.month - 1]}/{_MESES[ate.month - 1]}"
    return {"rotulos": rotulos, "valores": valores, "mes": mes}


def montar_resumo(launch: Any, d: dict, hm: Any, tmb: Any, cfg: dict, hoje: date) -> dict:
    meta, google, vendas, wa_cost = d.get("meta"), d.get("google"), d.get("vendas"), d.get("wa_cost")
    wa_gasto = _f((wa_cost or {}).get("total_cost_brl")) if wa_cost else 0.0

    receita = _f(getattr(vendas, "total_receita", 0))
    n_vendas = int(getattr(vendas, "total_vendas", 0) or 0)
    invest = _f(getattr(meta, "total_gasto", 0)) + _f(getattr(google, "total_custo", 0)) + wa_gasto

    # Vendas por produto (Hotmart + TMB somados). O `produto` do TMB traz a oferta no fim
    # ("… - TJSP - Lead17990"): tira o sufixo para a mesma Mentoria não virar várias barras.
    # Oferta avulsa de outro produto (ex.: upsell da Black) segue em barra própria.
    soma: dict[str, int] = {}
    for p in list(getattr(hm, "produtos", None) or []) + list(getattr(tmb, "produtos", None) or []):
        nome = p["nome"] if p.get("oferta_avulsa") else _SUFIXO_OFERTA.sub("", p["nome"]).strip()
        soma[nome] = soma.get(nome, 0) + int(p["qtd"])
    produtos = sorted(({"nome": n, "qtd": q} for n, q in soma.items()), key=lambda p: p["qtd"], reverse=True)

    # Modelo de pagamento: as 4 faixas exclusivas que já alimentam o debriefing.
    pg = getattr(hm, "pagamentos", None) or []
    pagamento = [
        {"rotulo": "À vista", "qtd": sum(int(p.get("a_vista") or 0) for p in pg)},
        {"rotulo": "Parcelado em 12x", "qtd": sum(int(p.get("parcelado_12x") or 0) for p in pg)},
        {"rotulo": "Outras parcelas", "qtd": sum(int(p.get("parcelado_outros") or 0) for p in pg)},
        {"rotulo": "Entrada (boleto parcelado)", "qtd": int(getattr(vendas, "tmb_vendas", 0) or 0)},
    ]

    ultimas = [s for s in (getattr(hm, "ultima_venda", ""), getattr(tmb, "ultima_venda", "")) if s]
    ultima = datetime.strptime(max(ultimas), "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M:%S") if ultimas else ""

    emails = set(getattr(vendas, "emails_hotmart", set()) or set()) | set(getattr(vendas, "emails_tmb", set()) or set())
    perfil = read_perfil_compradores(launch.code, emails, _safe_date(cfg.get("carrinho_start_date")))

    return {
        "titulo": f"DADOS DE VENDAS - {titulo_do_lancamento(launch.code)}",
        "receita": receita, "n_vendas": n_vendas,
        "ticket": (receita / n_vendas) if n_vendas else 0.0,
        "invest": invest, "roas": (receita / invest) if invest > 0 else 0.0,
        "lucro": receita - invest,
        "produtos": produtos,
        "dias": _dias_do_carrinho(cfg, hm, tmb, hoje),
        "pagamento": pagamento,
        "perfil": perfil,
        "ultima_venda": ultima,
        "tem_dados": n_vendas > 0,
    }
