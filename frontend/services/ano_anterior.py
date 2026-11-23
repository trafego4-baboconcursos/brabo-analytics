"""Comparação com o ano anterior no resumo de /lancamentos (PLANO_BACKFILL_2025, etapa 6).

Três peças, todas funções puras sobre o que a rota já calcula:
- a faixa "Lançamentos vs <ano anterior>": faturamento, investimento, ROAS, matrículas e custo por
  matrícula dos lançamentos nos MESMOS meses fechados dos dois anos (nunca ano cheio contra ano em andamento);
- a linha "vs PI-JAN-25" em cada cartão, pelo par produto + mês do código;
- a série do ano anterior, tracejada, no gráfico "Faturamento mês a mês".

Só lançamentos: 2025 não tem perpétuo nem distribuição com a mesma classificação. Leads ficam de fora
(o plano não compara leads/CPL entre os anos).
"""
from __future__ import annotations

from datetime import date

_MESES = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")


def codigo_par(code: str) -> str | None:
    """PI-JAN-26 → PI-JAN-25. Código fora do padrão PREFIXO-MÊS-AA (ex.: BV-26) não tem par."""
    partes = str(code or "").upper().split("-")
    if len(partes) != 3 or not partes[2].isdigit() or len(partes[2]) != 2:
        return None
    return f"{partes[0]}-{partes[1]}-{int(partes[2]) - 1:02d}"


def pares_do_ano(codes_ano, codes_ant) -> dict[str, str]:
    """{código do ano: código do ano anterior}, só quando o par existe no ano anterior."""
    existentes = {str(c).upper() for c in codes_ant}
    saida = {}
    for c in codes_ano:
        par = codigo_par(c)
        if par and par in existentes:
            saida[c] = par
    return saida


def ultimo_mes_fechado(ano: int, hoje: date) -> int:
    """Último mês inteiro já encerrado de `ano` (0 = nenhum)."""
    if hoje.year > ano:
        return 12
    if hoje.year < ano:
        return 0
    return hoje.month - 1


def _var(atual: float, anterior: float) -> float | None:
    return (atual - anterior) / anterior * 100 if anterior > 0 else None


def _derivados(receita: float, invest: float, vendas: float) -> dict:
    return {"receita": receita, "invest": invest, "vendas": int(round(vendas)),
            "roas": receita / invest if invest > 0 else 0.0,
            "cac": invest / vendas if vendas > 0 else 0.0}


def comparar_meses(mensal: dict, mensal_ant: dict, ate_mes: int) -> dict | None:
    """Soma dos meses 1..ate_mes nos dois anos e a variação em %. None sem mês fechado ou sem ano anterior."""
    if ate_mes <= 0 or not mensal or not mensal_ant:
        return None

    def _soma(m):
        meses = m["meses"][:ate_mes]
        return _derivados(sum(x["receita"] for x in meses), sum(x["invest"] for x in meses),
                          sum(x["vendas"] for x in meses))

    atual, ant = _soma(mensal), _soma(mensal_ant)
    if ant["receita"] <= 0 and ant["invest"] <= 0:
        return None
    var = {k: _var(atual[k], ant[k]) for k in ("receita", "invest", "vendas")}
    var["roas"] = _var(atual["roas"], ant["roas"])
    var["cac"] = _var(atual["cac"], ant["cac"])
    periodo = "o ano todo" if ate_mes == 12 else (_MESES[0] if ate_mes == 1 else f"{_MESES[0]}–{_MESES[ate_mes - 1]}")
    return {"ate_mes": ate_mes, "periodo": periodo, "atual": atual, "anterior": ant, "var": var}


def _rot(v: float) -> str:
    v = float(v or 0)
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}".replace(".", ",") + " mi"
    if v >= 1_000:
        return f"{v / 1_000:.0f} mil"
    return f"{v:.0f}" if v else ""


def anexar_serie_anterior(mensal: dict, mensal_ant: dict, ano_ant: int) -> dict:
    """Põe o faturamento do ano anterior em cada mês e refaz a escala do gráfico com ele incluído."""
    for m, a in zip(mensal["meses"], mensal_ant["meses"]):
        m["receita_ant"] = float(a["receita"])
        m["receita_ant_rot"] = _rot(a["receita"])
    teto = max([m["receita"] for m in mensal["meses"]] + [m["invest"] for m in mensal["meses"]]
               + [m["receita_ant"] for m in mensal["meses"]] + [0.0])
    for m in mensal["meses"]:
        m["h_receita"] = m["receita"] / teto * 100 if teto > 0 else 0.0
        m["h_invest"] = m["invest"] / teto * 100 if teto > 0 else 0.0
        m["h_ant"] = m["receita_ant"] / teto * 100 if teto > 0 else 0.0
    mensal["ano_anterior"] = ano_ant
    return mensal


def cartao_vs(atual: dict, anterior: dict, code_ant: str, fechado: bool) -> dict | None:
    """Linha "vs PI-JAN-25" do cartão. A variação só aparece com o carrinho do lançamento atual encerrado;
    antes disso o cartão mostra só quanto o do ano anterior fechou."""
    rec_ant = float((anterior or {}).get("receita") or 0)
    if rec_ant <= 0:
        return None
    rec = float((atual or {}).get("receita") or 0)
    return {"code": code_ant, "receita_ant": rec_ant, "roas_ant": float(anterior.get("roas") or 0),
            "fechado": fechado, "var_receita": _var(rec, rec_ant) if fechado and rec > 0 else None}


def fontes_faltando(launch) -> list[str]:
    """Fontes comparadas que não têm nenhum dado do lançamento no banco (leads não entram na comparação)."""
    falta = []
    if not getattr(launch, "has_meta", True):
        falta.append("Meta")
    if not getattr(launch, "has_google", True):
        falta.append("Google/YouTube")
    if not getattr(launch, "has_vendas", True):
        falta.append("Vendas")
    return falta
