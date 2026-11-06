"""Conciliação da comissão do time comercial: sistema (banco) x planilha consolidada.

    python scripts/comercial_conciliar.py --mes 2026-10 \
        --planilha ".../Análise Comercial 2026/Vendas - Por Vendedor 2026.xlsx" --saida <pasta>

Só leitura no banco. Cadastros vêm das planilhas em memória (`cadastros_da_planilha`, R5).
A saída é venda a venda, só com código da transação (nada de nome/e-mail/telefone/CPF) e fica
fora do git.
"""
from __future__ import annotations

import argparse
import calendar
import sys
import time
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

COLUNAS = ["transacao", "vendedor_planilha", "vendedor_sistema", "base_planilha", "base_sistema",
           "pct_planilha", "pct_sistema", "tipo_planilha", "tipo_sistema", "valor_planilha",
           "valor_sistema", "causa", "detalhe"]
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]
_TOL = Decimal("0.01")       # dinheiro
_TOL_PCT = Decimal("0.00001")  # percentual (0,02 x 0,015 difere em 0,005 < 0,01)
_PAGAS = ("elegivel", "prevista")


def _norm(txt) -> str:
    s = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def _col(df: pd.DataFrame, nome: str) -> str:
    alvo = _norm(nome)
    for c in df.columns:
        if _norm(c) == alvo:
            return c
    raise KeyError(f"coluna '{nome}' não encontrada")


def _transacao(v) -> str | None:
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


def _dec(v) -> Decimal | None:
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    return Decimal(str(v))


def ler_planilha(caminho: str | Path, ano: int, mes: int) -> pd.DataFrame:
    """Aba VENDAS filtrada pelo "Mês Ano" -> transacao, vendedor, tipo, pct, base, valor."""
    head = pd.read_excel(caminho, sheet_name="VENDAS", nrows=0)
    nomes = ("TRANSAÇÃO", "NOME", "TIPO", "% COMISSÃO", "VALOR CURSO", "VLR COMISSÃO", "Mês Ano")
    cols = [_col(head, n) for n in nomes]
    df = pd.read_excel(caminho, sheet_name="VENDAS", usecols=cols)[cols]
    df.columns = ["transacao", "vendedor", "tipo", "pct", "base", "valor", "mes_ano"]
    alvo = _norm(f"{mes} - {MESES[mes - 1]}")
    df = df[df["mes_ano"].map(_norm) == alvo].copy()
    df["transacao"] = df["transacao"].map(_transacao)
    for c in ("pct", "base", "valor"):
        df[c] = df[c].map(_dec)
    del df["mes_ano"]
    return df.dropna(subset=["transacao"]).reset_index(drop=True)


def _detalhe(l) -> str:
    if l is None:
        return ""
    return l.situacao + (f":{l.motivo}" if l.motivo else "")


def _iguais_dec(a, b, tol: Decimal = _TOL) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(Decimal(a) - Decimal(b)) < tol


def conciliar(linhas_sistema, df_planilha: pd.DataFrame,
              completadas: frozenset[str] = frozenset()) -> pd.DataFrame:
    """Casa por transação (papel "venda") e classifica a causa da diferença.

    `linhas_sistema`: LinhaComissao (só papel venda é usado); valor do sistema = 0 quando a
    linha não é elegível/prevista. `df_planilha`: colunas transacao, vendedor, tipo, pct, base,
    valor. Causa: ok | so_planilha | so_sistema | vendedor | tipo | base | pct (a primeira
    dimensão que diverge, nessa ordem); linha do sistema que existe mas não paga, com as
    dimensões iguais, sai como so_planilha (o `detalhe` diz por quê).
    `completadas`: transações cujo vendedor o sistema só acertou porque a atribuição foi
    completada a partir da planilha; o `detalhe` leva `atribuicao_completada`.
    """
    sis = {l.transacao: l for l in linhas_sistema if l.papel == "venda"}
    pla = {r.transacao: r for r in df_planilha.itertuples(index=False)}
    linhas = []
    for tr in list(pla) + [t for t in sis if t not in pla]:
        p, s = pla.get(tr), sis.get(tr)
        v_s = (s.valor if s.situacao in _PAGAS else Decimal("0")) if s else None
        reg = {
            "transacao": tr,
            "vendedor_planilha": p.vendedor if p else None,
            "vendedor_sistema": s.beneficiario if s else None,
            "base_planilha": p.base if p else None, "base_sistema": s.valor_base if s else None,
            "pct_planilha": p.pct if p else None, "pct_sistema": s.pct if s else None,
            "tipo_planilha": p.tipo if p else None, "tipo_sistema": s.tipo if s else None,
            "valor_planilha": p.valor if p else None, "valor_sistema": v_s,
            "detalhe": (_detalhe(s) + (" atribuicao_completada" if tr in completadas else "")).strip(),
        }
        if s is None:
            causa = "so_planilha"
        elif p is None:
            causa = "so_sistema"
        elif _norm(p.vendedor) != _norm(s.beneficiario):
            causa = "vendedor"
        elif _iguais_dec(p.valor or Decimal("0"), v_s):
            causa = "ok"
        elif _norm(p.tipo) != _norm(s.tipo):
            causa = "tipo"
        elif not _iguais_dec(p.base, s.valor_base):
            causa = "base"
        elif not _iguais_dec(p.pct, s.pct, _TOL_PCT):
            causa = "pct"
        else:
            causa = "so_planilha"
        reg["causa"] = causa
        linhas.append(reg)
    return pd.DataFrame(linhas, columns=COLUNAS)


# ---------------------------------------------------------------- execução

def _fmt(v) -> str:
    v = Decimal(v).quantize(Decimal("0.01"))
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ultimo_dia(ano: int, mes: int) -> date:
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mes", required=True, help="AAAA-MM")
    ap.add_argument("--planilha", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--pasta-cadastros", default=None,
                    help="pasta das planilhas (padrão: subindo a partir da --planilha)")
    ap.add_argument("--live", "--aulas", dest="live", action="append", default=[],
                    metavar="LANC=AAAA-MM-DD",
                    help="simula outra data da live para um lançamento (exceção editável, "
                         "§5.3); não grava nada")
    a = ap.parse_args()

    from scripts.comercial_carga_inicial import (
        CODIGO_POR_NOME, cadastros_da_planilha, montar_atribuicoes,
    )
    from frontend.db_readers.comercial import ler_janelas, ler_vendas
    from frontend.services.comercial.calculo import calcular, resumo_por_beneficiario

    ano, mes = (int(x) for x in a.mes.split("-"))
    inicio, fim = date(ano, mes, 1), _ultimo_dia(ano, mes)
    seg = date(ano + (mes == 12), mes % 12 + 1, 1)
    fim_seg = _ultimo_dia(seg.year, seg.month)
    hoje = datetime(fim_seg.year, fim_seg.month, fim_seg.day)

    planilha = Path(a.planilha)
    pasta = Path(a.pasta_cadastros) if a.pasta_cadastros else planilha.parent.parent
    cad = cadastros_da_planilha(pasta)
    df_p = ler_planilha(planilha, ano, mes)
    # a planilha escreve "Rafael" para o AT12: nome canônico = o do cadastro
    canon = {_norm(n): cad.vendedores.get(c, n) for n, c in CODIGO_POR_NOME.items()}
    df_p["vendedor"] = df_p["vendedor"].map(lambda n: canon.get(_norm(n), n))
    trans_planilha = frozenset(df_p["transacao"])

    t0 = time.perf_counter()
    vendas = ler_vendas(inicio, fim, transacoes_extra=frozenset(cad.atribuicoes) | trans_planilha,
                        ofertas=cad.ofertas, incluir_extra_fora_do_periodo=True)
    t_vendas = time.perf_counter() - t0
    live = {lanc: date.fromisoformat(dia) for lanc, dia in (x.split("=") for x in a.live)}
    janelas, sem_data = ler_janelas(inicio, fim, live)
    for j in janelas:
        if j.lancamento in live:
            print(f"janela {j.lancamento} simulada: {j.inicio:%d/%m %H:%M} -> {j.fim:%d/%m %H:%M}")
    vendas = [v for v in vendas if inicio <= v.data.date() <= fim or v.transacao in trans_planilha]
    # atribuições da carga comparam com o código da base da planilha; aqui completa com o
    # código que o banco dá (base da planilha e banco divergem em alguns pedidos TMB)
    codigo_banco = {v.transacao: (None if v.conflito_codigo else v.codigo_at) for v in vendas}
    extra = montar_atribuicoes(df_p.rename(columns={"vendedor": "nome"}), codigo_banco,
                               {**CODIGO_POR_NOME, **{n: c for c, n in cad.vendedores.items()}})
    novas = {t: c for t, c in extra.items() if t not in cad.atribuicoes and t in codigo_banco}
    cad.atribuicoes.update(novas)
    if novas:
        print(f"atribuições completadas pelo código do banco: {len(novas)} ({', '.join(sorted(novas))})")
    linhas = calcular(vendas, cad, janelas, hoje)
    # venda sem código e sem atribuição que a planilha não tem: não é do time, fica fora
    fora = {l.transacao for l in linhas if l.papel == "venda" and l.motivo == "sem_codigo"
            and l.transacao not in trans_planilha}
    linhas = [l for l in linhas if l.transacao not in fora]
    fora_mes = {v.transacao: v.data.date() for v in vendas if not inicio <= v.data.date() <= fim}

    df = conciliar(linhas, df_p, frozenset(novas))
    for tr, d in fora_mes.items():
        m = df["transacao"] == tr
        df.loc[m, "detalhe"] = (df.loc[m, "detalhe"] + f" fora_do_mes:{d.isoformat()}").str.strip()

    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    arq = saida / f"conciliacao_{a.mes}.csv"
    df.to_csv(arq, index=False, encoding="utf-8-sig")

    resumo = resumo_por_beneficiario([l for l in linhas if l.papel == "venda"])
    part = resumo_por_beneficiario([l for l in linhas if l.papel == "participacao"])
    plan = df_p.groupby("vendedor")["valor"].apply(lambda s: sum(s, Decimal("0")))
    nomes = sorted(set(resumo) | set(plan.index), key=_norm)
    print(f"Conciliação {a.mes}  (janelas: {[j.lancamento for j in janelas]}; "
          f"ler_vendas {t_vendas:.1f}s; {len(vendas)} vendas)")
    print(f"{'vendedor':<18}{'sistema':>14}{'planilha':>14}{'diferença':>14}")
    ts = tp = Decimal("0")
    for n in nomes:
        s = resumo.get(n, {}).get("total", Decimal("0"))
        p = plan.get(n, Decimal("0"))
        ts, tp = ts + s, tp + p
        print(f"{n:<18}{_fmt(s):>14}{_fmt(p):>14}{_fmt(s - p):>14}")
    print(f"{'TOTAL':<18}{_fmt(ts):>14}{_fmt(tp):>14}{_fmt(ts - tp):>14}")
    for n, r in part.items():
        print(f"participação {n}: {_fmt(r['total'])} (Ativa {_fmt(r['Ativa'])}, "
              f"Reativa {_fmt(r['Reativa'])}) — não está na planilha")
    print("\ncausas:")
    for causa, g in df.groupby("causa"):
        dif = sum((Decimal(x or 0) for x in g["valor_sistema"]), Decimal("0")) - \
            sum((Decimal(x or 0) for x in g["valor_planilha"]), Decimal("0"))
        print(f"  {causa:<12}{len(g):>5}  impacto sistema-planilha {_fmt(dif):>12}")
    print(f"vendas sem código fora da planilha (não listadas): {len(fora)}")
    comp = [l for l in linhas if l.papel == "venda" and l.transacao in novas]
    print(f"\natribuições completadas a partir da planilha (o sistema sozinho não acharia o "
          f"vendedor): {len(comp)}")
    por: dict[str, list] = {}
    for l in comp:
        e = por.setdefault(l.beneficiario, [0, Decimal("0")])
        e[0] += 1
        e[1] += l.valor if l.situacao in _PAGAS else Decimal("0")
    for n, (q, v) in sorted(por.items(), key=lambda kv: _norm(kv[0])):
        print(f"  {n:<16}{q:>4} vendas  {_fmt(v):>10}")
    print("\nALERTA: lançamentos sem data da live (sem janela Reativa; vendas deles contam como Ativa):")
    sufixo = f"-{MESES[mes - 1][:3].upper()}-{ano % 100:02d}".replace("Ç", "C")
    if not sem_data:
        print("  nenhum")
    for lanc, hm, tm in sem_data:
        marca = "  <- do mês" if _norm(lanc).upper().endswith(_norm(sufixo).upper()) else ""
        print(f"  {lanc:<12} hotmart={','.join(sorted(hm)) or '-'} tmb={','.join(sorted(tm)) or '-'}{marca}")
    print(f"CSV: {arq}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
