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


def conferir_reivindicacao(linha: LinhaComissao | None, codigo: str) -> None:
    """Recusa o que não faz sentido pedir: venda já atribuída à mão ou já no código de quem
    pede. Venda fora do mês guardado (linha None) segue: o gestor decide."""
    from frontend.db_readers.comercial import EscritaRecusada  # noqa: PLC0415
    if linha is None:
        return
    if linha.atribuicao_manual:
        raise EscritaRecusada("ja_atribuida")
    if linha.vendedor_codigo == codigo and linha.motivo != "conflito_codigo":
        raise EscritaRecusada("ja_e_sua")


def localizar(linhas: list[LinhaComissao] | None, transacao: str) -> LinhaComissao | None:
    for l in linhas or ():
        if l.papel == "venda" and l.transacao == transacao:
            return l
    return None


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
        "pendentes": list(fila.get("pendentes", [])),
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
        r = snap.StoreBanco().get(mes)
    except Exception:  # noqa: BLE001 — sem snapshot, a ação segue e invalida todos os meses
        import logging  # noqa: PLC0415
        logging.getLogger("comercial.inconsistencias").exception("linhas_guardadas(%s)", mes)
        return None
    return r.linhas if r else None
