"""Tela de Inconsistências da área Comercial (Task 6): fila + ações do gestor/vendedor.

O isolamento mora AQUI: o vendedor recebe só a busca de vendas sem código (que não têm dono)
e os PRÓPRIOS pedidos; pendências de venda (reembolso, conflito, base, regra), pedidos dos
outros e o histórico só vão para o view-model do gestor. O template só desenha.

As ações validam a entrada (`EntradaInvalida` -> 400) e chamam as escritas exatas de
`frontend/db_readers/comercial.py` (recusa de estado -> `EscritaRecusada` -> 303 com erro).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from frontend.services.comercial.acesso import AcessoComercial, pode
from frontend.services.comercial.calculo import LinhaComissao
from frontend.services.comercial.snapshot import ResultadoMes

LIMITE_LISTA = 200          # nunca despejar as ~800 vendas sem código do mês
BUSCA_MIN_VENDEDOR = 4      # vendedor só vê a lista quando busca (não "pesca" vendas alheias)
_RE_CODIGO = re.compile(r"^AT\d{1,4}$")
_RE_TRANSACAO = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_RE_VENDEDOR_AUTO = re.compile(r"^Vendedor \d+$")
MAX_TEXTO = 1000

MENSAGENS_OK = {
    "reivindicada": "Pedido enviado. Fica pendente até o gestor aprovar.",
    "aprovada": "Atribuição aprovada. A comissão do mês será recalculada na próxima abertura.",
    "recusada": "Pedido recusado.",
    "atribuida": "Venda atribuída ao vendedor.",
    "reembolso": "Decisão de reembolso registrada.",
    "ajuste": "Ajuste manual registrado.",
}
MENSAGENS_ERRO = {
    "ja_reivindicada": "Essa venda já tem um pedido em análise.",
    "ja_atribuida": "Essa venda já está atribuída a um vendedor.",
    "ja_recusada": "O pedido dessa venda já foi recusado. Fale com o gestor.",
    "ja_aprovada": "Esse pedido já estava aprovado — nada foi duplicado.",
    "ja_decidida": "Esse pedido já foi decidido.",
    "nao_encontrada": "Pedido não encontrado.",
    "ja_e_sua": "Essa venda já está no seu código.",
    "nao_invalidou": "Gravado, mas o cálculo guardado do mês não foi marcado: use Recalcular.",
    "venda_nao_encontrada": "Venda não encontrada no mês. Confira o código e o mês da venda.",
    "de_outro": "Essa venda já está no código de outro vendedor.",
    "conflito_gestor": "Essa venda tem conflito de código que só o gestor resolve.",
    "ajuste_concorrente": "Outro ajuste desta venda foi gravado ao mesmo tempo. Confira o histórico e tente de novo.",
    "mes_fechado": "Mês fechado — reabra para alterar.",
}


class EntradaInvalida(ValueError):
    """Campo faltando ou fora do formato: 400 com a mensagem."""


# ---------------------------------------------------------------- entrada
def plataforma_de(transacao: str) -> str:
    """Hotmart começa com 'HP'; o resto é pedido TMB."""
    return "hotmart" if transacao.upper().startswith("HP") else "tmb"


def limpar_transacao(txt: str | None) -> str:
    t = (txt or "").strip()
    if not _RE_TRANSACAO.fullmatch(t):
        raise EntradaInvalida("Código da transação inválido.")
    return t.upper() if t.upper().startswith("HP") else t


def limpar_codigo(txt: str | None) -> str:
    c = (txt or "").strip().upper().replace(" ", "")
    if not _RE_CODIGO.fullmatch(c):
        raise EntradaInvalida("Código de vendedor inválido (use ATn).")
    return f"AT{int(c[2:])}"


def texto_obrigatorio(txt: str | None, campo: str) -> str:
    t = (txt or "").strip()
    if not t:
        raise EntradaInvalida(f"{campo} é obrigatório.")
    if len(t) > MAX_TEXTO:
        raise EntradaInvalida(f"{campo}: no máximo {MAX_TEXTO} caracteres.")
    return t


def _numero(txt: str | None) -> Decimal | None:
    t = (txt or "").strip().replace("R$", "").replace("%", "").strip()
    if not t:
        return None
    if "," in t:  # formato brasileiro: 1.477,50
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):  # "1.477" / "12.345.678": ponto é milhar
        t = t.replace(".", "")
    try:
        d = Decimal(t)
    except InvalidOperation:
        raise EntradaInvalida("Número inválido.") from None
    if not d.is_finite():
        raise EntradaInvalida("Número inválido.")
    return d


def ler_ajuste(pct_txt: str | None, base_txt: str | None) -> tuple[Decimal | None, Decimal | None]:
    """'% digitado' (10 = 10%) -> fração 0.10; base em R$. Pelo menos um dos dois."""
    pct, base = _numero(pct_txt), _numero(base_txt)
    if pct is None and base is None:
        raise EntradaInvalida("Informe o percentual e/ou o valor-base do ajuste.")
    if pct is not None and not (Decimal("0") <= pct <= Decimal("100")):
        raise EntradaInvalida("Percentual entre 0 e 100.")
    if base is not None and not (Decimal("0") < base < Decimal("1000000")):
        raise EntradaInvalida("Valor-base entre R$ 0 e R$ 1.000.000.")
    return (None if pct is None else pct / Decimal("100")), base


# ---------------------------------------------------------------- regras das ações
def codigo_do_pedido(acesso: AcessoComercial, codigo_form: str | None) -> str:
    """Vendedor reivindica sempre para o PRÓPRIO código (o do formulário é ignorado);
    gestor informa para quem."""
    if pode(acesso.nivel, "aprovar"):
        return limpar_codigo(codigo_form)
    if not acesso.vendedor_codigo:
        raise EntradaInvalida("Seu acesso não tem código de vendedor.")
    return acesso.vendedor_codigo


def mes_obrigatorio(mes_txt: str | None, hoje: date) -> date:
    """Ruling 14: a reivindicação precisa do mês da venda (válido, na janela da Task 5)."""
    from frontend.services.comercial import telas  # noqa: PLC0415
    if not (mes_txt or "").strip():
        raise EntradaInvalida("Informe o mês da venda.")
    try:
        return telas.resolver_periodo(mes_txt, None, None, hoje).mes
    except telas.PeriodoInvalido as exc:
        raise EntradaInvalida(str(exc)) from None


def conferir_reivindicacao(linha: LinhaComissao | None, codigo: str,
                           codigos_conflito: tuple | None = None) -> None:
    """Ruling 14 — só se reivindica venda ACHADA no mês e reivindicável: sem código; ou
    conflito TMB em que quem pede é um dos dois códigos (sem os dois códigos à mão, só o
    gestor resolve). Venda no código de outro -> `de_outro`; no próprio -> `ja_e_sua`."""
    from frontend.db_readers.comercial import EscritaRecusada  # noqa: PLC0415
    if linha is None:
        raise EscritaRecusada("venda_nao_encontrada")
    if linha.atribuicao_manual:
        raise EscritaRecusada("ja_atribuida")
    if linha.motivo == "sem_codigo":
        return
    if linha.motivo == "conflito_codigo":
        cods = {c for c in (codigos_conflito or ()) if c}
        if len(cods) < 2:
            raise EscritaRecusada("conflito_gestor")
        if codigo not in cods:
            raise EscritaRecusada("de_outro")
        return
    if linha.vendedor_codigo == codigo:
        raise EscritaRecusada("ja_e_sua")
    raise EscritaRecusada("de_outro")


def linha_da_venda(mes: date, transacao: str) -> LinhaComissao | None:
    """Linha da venda no mês: snapshot guardado (sem recalcular); se não está lá, o cálculo
    do mês (obter_mes — pode recalcular). Roda em threadpool."""
    from frontend.services.comercial import snapshot as snap  # noqa: PLC0415
    linha = localizar(linhas_guardadas(mes), transacao)
    if linha is None:
        linha = localizar(snap.obter_mes(mes).linhas, transacao)
    return linha


def localizar(linhas: list[LinhaComissao] | None, transacao: str) -> LinhaComissao | None:
    for l in linhas or ():
        if l.papel == "venda" and l.transacao == transacao and l.situacao != "estorno":
            return l
    return None


def exigir_venda_de_mes_aberto(transacao: str, *, reembolso: bool = False) -> date | None:
    """Ruling 17/19/20 — "mês de efeito": recusa (`mes_fechado`) só se o efeito seria calculado
    num mês fechado. Venda nas linhas congeladas de um mês fechado: só a decisão de reembolso
    passa (o "tira" vira estorno no primeiro mês aberto depois) e devolve esse mês fechado, para
    a rota invalidar os seguintes. Venda fora de qualquer congelado (mês aberto, ou paga/ingerida
    depois do fechamento -> venda tardia no primeiro mês aberto): passa, devolve None."""
    from frontend.db_readers.comercial import EscritaRecusada, mes_fechado_da_transacao  # noqa: PLC0415
    mes = mes_fechado_da_transacao(transacao)
    if mes is not None and not reembolso:
        raise EscritaRecusada("mes_fechado")
    return mes


# ---------------------------------------------------------------- view-model
@dataclass(frozen=True)
class Conflito:
    linha: LinhaComissao
    codigos: tuple[str, ...]


def _vendas(linhas):
    return [l for l in linhas if l.papel == "venda"]


def sem_codigo(linhas: list[LinhaComissao], q: str | None) -> list[LinhaComissao]:
    q = (q or "").strip().upper()
    ls = [l for l in _vendas(linhas) if l.situacao == "inconsistente" and l.motivo == "sem_codigo"]
    if q:
        ls = [l for l in ls if q in l.transacao.upper()]
    return sorted(ls, key=lambda l: (l.data, l.transacao))


def codigos_novos(linhas: list[LinhaComissao]) -> list[tuple[str, str]]:
    """Código AT sem cadastro, nomeado 'Vendedor N' pelo motor (§5.1: aviso, não bloqueia)."""
    vistos = {l.vendedor_codigo: l.beneficiario for l in _vendas(linhas)
              if l.vendedor_codigo and _RE_VENDEDOR_AUTO.fullmatch(l.beneficiario or "")}
    return sorted(vistos.items(), key=lambda kv: int(kv[0][2:]) if kv[0][2:].isdigit() else 0)


def _com_dono(pedido: dict, vendas: list[LinhaComissao]) -> dict:
    """Ruling 14c: ao lado do pedido, o dono atual da venda e o motivo (do cálculo do mês)."""
    linha = localizar(vendas, pedido["transacao"])
    if linha is None:
        return {**pedido, "dono": None, "dono_motivo": "fora deste mês", "de_outro": False}
    dono = f"{linha.beneficiario} ({linha.vendedor_codigo})" if linha.vendedor_codigo else "sem código"
    return {**pedido, "dono": dono, "dono_motivo": linha.motivo,
            "de_outro": bool(linha.vendedor_codigo) and linha.vendedor_codigo != pedido.get("vendedor_codigo")}


def view_inconsistencias(res: ResultadoMes, periodo, acesso: AcessoComercial, fila: dict,
                         conflitos: dict[str, tuple] | None = None, q: str | None = None) -> dict:
    gestor = pode(acesso.nivel, "aprovar")
    q = (q or "").strip()[:64]
    todas_sem = sem_codigo(res.linhas, q)
    total_mes = len(todas_sem) if not q else len(sem_codigo(res.linhas, None))
    if not gestor and len(q) < BUSCA_MIN_VENDEDOR:
        lista = []  # vendedor: só com busca
    else:
        lista = todas_sem[:LIMITE_LISTA]
    base = {
        "periodo": periodo, "gerado_em": res.gerado_em, "gestor": gestor, "acesso": acesso,
        "fechado": res.fechado, "fechado_em": res.fechado_em, "fechado_por": res.fechado_por,
        "sem_livre": True, "q": q,
        "sem_codigo": lista, "sem_codigo_total": total_mes, "sem_codigo_achadas": len(todas_sem),
        "sem_codigo_cortado": len(todas_sem) > len(lista) and bool(lista),
        "busca_min": BUSCA_MIN_VENDEDOR,
        "com_pedido": set(fila.get("com_pedido") or ()),
    }
    if not gestor:
        meu = acesso.vendedor_codigo
        return {**base, "minhas": [p for p in fila.get("minhas", []) if p["vendedor_codigo"] == meu],
                "pendentes": [], "reembolso": [], "conflitos": [], "sem_base": [], "sem_regra": [],
                "codigos_novos": [], "historico": [], "vendedores": []}
    vendas = _vendas(res.linhas)
    conflitos = conflitos or {}
    ordem = lambda ls: sorted(ls, key=lambda l: (l.data, l.transacao))  # noqa: E731
    return {
        **base,
        "minhas": [],
        "pendentes": [_com_dono(p, vendas) for p in fila.get("pendentes", [])],
        "reembolso": ordem(l for l in vendas if l.situacao == "reembolso_a_verificar"),
        "conflitos": [Conflito(l, tuple(c for c in dict.fromkeys(conflitos.get(l.transacao, ())) if c))
                      for l in ordem(l for l in vendas
                                     if l.situacao == "inconsistente" and l.motivo == "conflito_codigo")],
        "sem_base": ordem(l for l in vendas if l.situacao == "inconsistente" and l.motivo == "sem_valor_base"),
        "sem_regra": ordem(l for l in vendas if l.situacao == "inconsistente" and l.motivo == "sem_regra"),
        "codigos_novos": codigos_novos(res.linhas),
        "historico": list(fila.get("historico", [])),
        "vendedores": list(fila.get("vendedores", [])),
    }


def mes_valido(mes_txt: str | None, hoje: date):
    """Mês do formulário -> date (1º dia) ou None se ausente/inválido (invalida todos)."""
    from frontend.services.comercial import telas  # noqa: PLC0415
    if not (mes_txt or "").strip():
        return None
    try:
        return telas.resolver_periodo(mes_txt, None, None, hoje).mes
    except telas.PeriodoInvalido:
        return None


def linhas_guardadas(mes: date | None) -> list[LinhaComissao] | None:
    """Linhas do snapshot gravado do mês, mesmo desatualizado, SEM recalcular (uma ação não
    pode custar ~20 s de cálculo). Serve para validar o pedido e achar o mês a invalidar."""
    from frontend.services.comercial import snapshot as snap  # noqa: PLC0415
    if mes is None:
        return None
    try:
        st = snap.StoreBanco()
        r = st.fechamento(mes) or st.get(mes)  # mês fechado: a cópia congelada
    except Exception:  # noqa: BLE001 — sem snapshot, a ação segue e invalida todos os meses
        import logging  # noqa: PLC0415
        logging.getLogger("comercial.inconsistencias").exception("linhas_guardadas(%s)", mes)
        return None
    return r.linhas if r else None
