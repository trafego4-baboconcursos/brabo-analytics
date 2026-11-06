"""Tela "Regras e vendedores" da área Comercial (Task 7a): validação da entrada e view-model.

Só gestor (master/coordenador) chega aqui — a rota checa `pode(nivel, ...)` antes. As escritas
são as declarações exatas de `frontend/db_readers/comercial.py` (Ruling 15: editar %, valor-base
ou participação = VERSIONAR — fecha a linha vigente e abre outra a partir da data escolhida).
Entrada fora do formato -> `EntradaInvalida` (400); estado do banco não deixa -> `EscritaRecusada`
(303 com código de mensagem).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from frontend.services.comercial.meses import PRIMEIRO_MES, soma_meses
from frontend.services.comercial.inconsistencias import (  # noqa: F401  (reexportados para a rota)
    EntradaInvalida, _numero, limpar_codigo,
)

PLATAFORMAS = {"hotmart": "Hotmart", "tmb": "TMB"}
MODALIDADES = {"cartao_pix": "Cartão / Pix / à vista", "parcelado": "Parcelado / boleto / recorrência"}
TIPOS = ("Ativa", "Reativa")
NIVEIS = {"master": "Master", "coordenador": "Coordenador", "vendedor": "Vendedor"}
INICIO_MINIMO = PRIMEIRO_MES  # piso único (meses.py)
LIMITE_LISTA = 200
MAX_NOME = 80
MAX_TEXTO = 1000
# conservador de propósito: sem aspas, <, >, parênteses, espaço nem barra invertida
_RE_EMAIL = re.compile(r"^[a-z0-9._%+-]{1,64}@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,24}$")
_RE_PRECO = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_RE_LANC = re.compile(r"^[A-Za-z0-9-]{2,32}$")

MENSAGENS_OK = {
    "vendedor_criado": "Vendedor cadastrado.",
    "vendedor_renomeado": "Nome do vendedor atualizado. As telas recalculam na próxima abertura.",
    "vendedor_ativo": "Situação do vendedor atualizada.",
    "acesso_gravado": "Acesso gravado. Vale no próximo clique da pessoa.",
    "acesso_removido": "Acesso removido.",
    "regra_versionada": "Nova versão do percentual gravada; a anterior foi encerrada na véspera.",
    "regra_criada": "Regra de percentual cadastrada.",
    "regra_encerrada": "Regra encerrada.",
    "part_versionada": "Nova versão da participação gravada; a anterior foi encerrada na véspera.",
    "part_criada": "Participação cadastrada.",
    "part_encerrada": "Participação encerrada.",
    "base_versionada": "Nova versão do valor-base gravada; a anterior foi encerrada na véspera.",
    "base_criada": "Valor-base cadastrado.",
    "oferta_gravada": "Oferta gravada.",
    "janela_gravada": "Janela Reativa manual gravada.",
    "janela_removida": "Janela manual removida: vale de novo a data do launch_config.",
    "meta_gravada": "Meta gravada.",
    "bonus_gravado": "Bônus gravado.",
    "mes_fechado_ok": "Mês fechado: as linhas, o bônus e os totais ficaram congelados.",
    "mes_reaberto": "Mês reaberto: volta a ser calculado ao vivo na próxima abertura.",
}
MENSAGENS_ERRO = {
    "vendedor_existe": "Esse código já está cadastrado. Para trocar o nome, use Renomear.",
    "vendedor_nao_encontrado": "Vendedor não cadastrado. Cadastre o código primeiro.",
    "sem_mudanca": "Nada mudou: o valor informado é igual ao atual.",
    "acesso_nao_encontrado": "Esse e-mail não tem acesso cadastrado.",
    "nao_encontrada": "Registro não encontrado (a página pode estar desatualizada).",
    "versao_encerrada": "Essa linha já está encerrada; crie a nova versão a partir da linha vigente.",
    "versao_data": "A nova versão precisa começar depois do início da versão vigente.",
    "versao_concorrente": "Outra alteração desta linha foi gravada ao mesmo tempo. Confira e tente de novo.",
    "ja_existe_aberta": "Já existe uma linha vigente com essa mesma chave. Use Nova versão nela.",
    "sobrepoe_vigencia": "A data de início cai dentro de uma vigência já encerrada; isso mudaria o passado.",
    "duplicado": "Já existe uma linha com essa chave e essa data de início.",
    "janela_nao_encontrada": "Esse lançamento não tem janela manual.",
    "nao_invalidou": "Gravado, mas o cálculo guardado não foi marcado: use Recalcular no mês afetado.",
    "mes_fechado": "Mês fechado — reabra para alterar.",
    "ja_fechado": "Esse mês já está fechado.",
    "nao_fechado": "Esse mês não está fechado (outro gestor pode ter reaberto).",
    "mes_nao_terminou": "Só se fecha um mês que já terminou.",
    "tem_a_verificar": "Ainda há vendas com reembolso a verificar neste mês: decida em Inconsistências antes de fechar.",
    "mudou_durante_o_fechamento": "Algo foi gravado enquanto o mês era calculado para o fechamento. Nada foi fechado: tente de novo.",
    "reabrir_ordem": "Só o último mês fechado pode ser reaberto: reabra antes os meses seguintes.",
}


def _mes_fechado(mes: date) -> bool:
    """Ruling 17: mês fechado (comercial_fechamentos ativo) não aceita escrita com efeito nele."""
    from frontend.db_readers.comercial import mes_fechado  # noqa: PLC0415
    return mes_fechado(mes.replace(day=1))


def recusar_se_fechado(*meses: date) -> None:
    """Algum dos meses fechado -> EscritaRecusada("mes_fechado") (303 com a mensagem)."""
    from frontend.db_readers.comercial import EscritaRecusada  # noqa: PLC0415
    for m in sorted({m.replace(day=1) for m in meses if m}):
        if _mes_fechado(m):
            raise EscritaRecusada("mes_fechado")


# ---------------------------------------------------------------- entrada
def texto(txt: str | None, campo: str, maximo: int = MAX_NOME) -> str:
    t = " ".join((txt or "").split())
    if not t:
        raise EntradaInvalida(f"{campo} é obrigatório.")
    if len(t) > maximo:
        raise EntradaInvalida(f"{campo}: no máximo {maximo} caracteres.")
    return t


def texto_opcional(txt: str | None, campo: str, maximo: int = MAX_TEXTO) -> str | None:
    return texto(txt, campo, maximo) if (txt or "").strip() else None


def codigo_opcional(txt: str | None) -> str | None:
    return limpar_codigo(txt) if (txt or "").strip() else None


def escolha(txt: str | None, opcoes, campo: str) -> str:
    t = (txt or "").strip()
    if t not in opcoes:
        raise EntradaInvalida(f"{campo} inválido.")
    return t


def email(txt: str | None) -> str:
    e = (txt or "").strip().lower()
    if not _RE_EMAIL.fullmatch(e):
        raise EntradaInvalida("E-mail inválido.")
    return e


def pct(txt: str | None, campo: str = "Percentual") -> Decimal:
    """'4' ou '4,5' (por cento) -> fração 0.04 / 0.045. Obrigatório, entre 0 e 100."""
    p = _numero(txt)
    if p is None:
        raise EntradaInvalida(f"{campo} é obrigatório.")
    if not (Decimal("0") <= p <= Decimal("100")):
        raise EntradaInvalida(f"{campo}: entre 0 e 100.")
    return p / Decimal("100")


def reais(txt: str | None, campo: str, *, zero: bool = False) -> Decimal:
    """R$ em formato brasileiro ('1.477' = 1477; '1.477,50'). `zero` aceita 0."""
    v = _numero(txt)
    if v is None:
        raise EntradaInvalida(f"{campo} é obrigatório.")
    if not ((Decimal("0") <= v if zero else Decimal("0") < v) and v < Decimal("100000000")):
        raise EntradaInvalida(f"{campo}: valor fora do intervalo.")
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def proximo_mes(hoje: date) -> date:
    return soma_meses(hoje.replace(day=1), 1)


def data_inicio(txt: str | None, hoje: date, padrao: date | None = None) -> date:
    """Início da nova versão. Vazio = `padrao` (nova versão: 1º dia do mês corrente, SP;
    encerrar: 1º do mês seguinte). De 2026-01-01 a um ano à frente; nunca dentro de mês
    fechado (gancho da Task 7b)."""
    t = (txt or "").strip()
    if not t:
        d = padrao or hoje.replace(day=1)
    else:
        try:
            d = date.fromisoformat(t)
        except ValueError:
            raise EntradaInvalida("Data inválida: use AAAA-MM-DD.") from None
    if not (INICIO_MINIMO <= d <= hoje + timedelta(days=366)):
        raise EntradaInvalida(f"Data fora do intervalo ({INICIO_MINIMO:%d/%m/%Y} até um ano à frente).")
    recusar_se_fechado(d)  # a nova versão não pode começar dentro de mês fechado
    return d


def mes(txt: str | None, hoje: date, *, ate_proximo: bool = False, escrita: bool = True) -> date:
    """AAAA-MM -> 1º dia. Vazio = mês corrente. De 2026-01 até o mês corrente (meta: até o
    seguinte, para cadastrar com antecedência). Escrita em mês fechado -> `mes_fechado`
    (`escrita=False`: só leitura da tela, mês fechado se vê normalmente)."""
    t = (txt or "").strip()
    atual = hoje.replace(day=1)
    if not t:
        m = atual
    else:
        try:
            m = datetime.strptime(t, "%Y-%m").date()
        except ValueError:
            raise EntradaInvalida("Mês inválido: use AAAA-MM.") from None
    limite = soma_meses(atual, 1) if ate_proximo else atual
    if not (INICIO_MINIMO <= m <= limite):
        raise EntradaInvalida("Mês fora do intervalo disponível.")
    if escrita:
        recusar_se_fechado(m)
    return m


def momento(txt: str | None, campo: str, *, fim: bool) -> datetime:
    """'AAAA-MM-DDTHH:MM[:SS]' (datetime-local) ou 'AAAA-MM-DD' (início 00:00:00, fim 23:59:59)."""
    t = (txt or "").strip()
    if not t:
        raise EntradaInvalida(f"{campo} é obrigatório.")
    try:
        if len(t) == 10:
            d = date.fromisoformat(t)
            dt = datetime(d.year, d.month, d.day, 23, 59, 59) if fim else datetime(d.year, d.month, d.day)
        else:
            dt = datetime.fromisoformat(t)
    except ValueError:
        raise EntradaInvalida(f"{campo}: data/hora inválida.") from None
    if dt.tzinfo is not None:
        raise EntradaInvalida(f"{campo}: informe no horário de São Paulo, sem fuso.")
    if not (datetime(2025, 1, 1) <= dt <= datetime(2030, 12, 31, 23, 59, 59)):
        raise EntradaInvalida(f"{campo}: fora do intervalo.")
    return dt


def janela(inicio_txt: str | None, fim_txt: str | None) -> tuple[datetime, datetime]:
    ini = momento(inicio_txt, "Início", fim=False)
    fi = momento(fim_txt, "Fim", fim=True)
    if fi <= ini:
        raise EntradaInvalida("O fim da janela precisa ser depois do início.")
    if fi - ini > timedelta(days=62):
        raise EntradaInvalida("Janela de no máximo 62 dias.")
    return ini, fi


def categorias(marcadas: list[str] | None, conhecidas) -> list[str] | None:
    """Categorias da regra: só as conhecidas (valores-base + TMB); nada marcado = None (todas)."""
    from frontend.services.comercial.tabelas import categorias_ordenadas  # noqa: PLC0415
    cats = [" ".join(c.split()) for c in (marcadas or []) if (c or "").strip()]
    if not cats:
        return None
    fora = sorted(set(cats) - set(conhecidas))
    if fora:
        raise EntradaInvalida("Categoria desconhecida: " + ", ".join(fora[:3]))
    return categorias_ordenadas(cats)


def forca_tipo(txt: str | None, tipo: str) -> str | None:
    """Ruling 15: `forca_tipo` vazio ou igual ao tipo da regra (regra Ativa que força Ativa)."""
    t = (txt or "").strip()
    if not t:
        return None
    if t != tipo:
        raise EntradaInvalida("“Forçar tipo” só pode ser igual ao tipo da regra (ou vazio).")
    return t


def preco(txt: str | None) -> str:
    t = (txt or "").strip()
    if not _RE_PRECO.fullmatch(t):
        raise EntradaInvalida("Código do preço inválido.")
    return t


def lancamento(txt: str | None, conhecidos) -> str:
    t = (txt or "").strip().upper()
    if not _RE_LANC.fullmatch(t) or t not in set(conhecidos):
        raise EntradaInvalida("Lançamento não encontrado no launch_config.")
    return t


def conferir_acesso_proprio(alvo: str, autor: str, nivel_novo: str | None) -> None:
    """Ninguém remove o próprio acesso nem se rebaixa a vendedor (evita ficar trancado fora)."""
    if alvo != autor:
        return
    if nivel_novo is None:
        raise EntradaInvalida("Você não pode remover o seu próprio acesso.")
    if nivel_novo == "vendedor":
        raise EntradaInvalida("Você não pode rebaixar o seu próprio acesso.")


# ---------------------------------------------------------------- invalidação
def meses_desde(desde: date, hoje: date) -> list[date] | None:
    """Meses cujo cálculo guardado muda com uma regra que vale a partir de `desde`: do mês de
    `desde` até o corrente. Mais de 3 -> None (marca todos de uma vez)."""
    m, atual = desde.replace(day=1), hoje.replace(day=1)
    meses = []
    while m <= atual:
        meses.append(m)
        m = soma_meses(m, 1)
    return None if len(meses) > 3 else meses


def meses_da_janela(*janelas) -> list[date]:
    """Meses tocados pelas janelas (anterior e nova)."""
    out: set[date] = set()
    for j in janelas:
        if not j:
            continue
        m = j[0].date().replace(day=1)
        while m <= j[1].date().replace(day=1):
            out.add(m)
            m = soma_meses(m, 1)
    return sorted(out)


# ---------------------------------------------------------------- view-model
def _num_codigo(codigo: str) -> int:
    n = (codigo or "")[2:]
    return int(n) if n.isdigit() else 10**6


def grupos_regras(regras: list[dict]) -> list[dict]:
    """Uma entrada por chave (plataforma, modalidade, tipo, vendedor, categorias): a versão
    vigente (aberta) e o histórico das encerradas, mais recente primeiro."""
    from frontend.db_readers.comercial import chave_regra  # noqa: PLC0415
    por: dict[tuple, list[dict]] = {}
    for r in regras:
        por.setdefault(chave_regra(r), []).append(r)
    saida = []
    for chave, rs in por.items():
        rs = sorted(rs, key=lambda r: r["vigente_de"], reverse=True)
        atual = next((r for r in rs if r["vigente_ate"] is None), None)
        saida.append({"chave": chave, "plataforma": chave[0], "modalidade": chave[1], "tipo": chave[2],
                      "vendedor": chave[3] or None, "categorias": list(chave[4]),
                      "atual": atual, "historico": [r for r in rs if r is not atual]})
    return sorted(saida, key=lambda g: (bool(g["categorias"]), bool(g["vendedor"]),
                                        _num_codigo(g["vendedor"] or ""), g["categorias"],
                                        g["plataforma"], g["modalidade"], TIPOS.index(g["tipo"])
                                        if g["tipo"] in TIPOS else 9))


def grupos_participacoes(parts: list[dict]) -> list[dict]:
    por: dict[str, list[dict]] = {}
    for p in parts:
        por.setdefault(p["beneficiario"], []).append(p)
    saida = []
    for nome, ps in sorted(por.items()):
        ps = sorted(ps, key=lambda p: p["vigente_de"], reverse=True)
        atual = next((p for p in ps if p["vigente_ate"] is None), None)
        saida.append({"beneficiario": nome, "atual": atual, "historico": [p for p in ps if p is not atual],
                      "codigo": (atual or ps[0])["beneficiario_codigo"]})
    return saida


def filtrar_bases(bases: list[dict], q: str | None) -> tuple[list[dict], int]:
    """Valores-base filtrados por valor cobrado/base ('1477', '1.477,00') ou categoria; no
    máximo LIMITE_LISTA. Devolve (lista, total achado)."""
    q = (q or "").strip()[:64]
    ls = bases
    if q:
        alvo = None
        try:
            alvo = _numero(q)
        except EntradaInvalida:
            pass
        qn = q.casefold()
        ls = [b for b in bases if qn in (b["categoria"] or "").casefold()
              or (alvo is not None and alvo in (Decimal(b["valor_cobrado"]), Decimal(b["valor_base"])))]
    ls = sorted(ls, key=lambda b: (b["plataforma"], Decimal(b["valor_cobrado"]), b["vigente_de"]))
    return ls[:LIMITE_LISTA], len(ls)


def filtrar_ofertas(ofertas: list[dict], q: str | None) -> tuple[list[dict], int]:
    q = (q or "").strip()[:64].casefold()
    ls = [o for o in ofertas if not q or q in o["codigo_do_preco"].casefold()
          or q in (o["nome_deste_preco"] or "").casefold()]
    return ls[:LIMITE_LISTA], len(ls)


def linhas_janelas(lancamentos: list[tuple], manuais: dict) -> list[dict]:
    """Por lançamento do launch_config: data da live, janela automática, janela manual e a que
    está EM VIGOR (manual vence a automática — mesma fonte de `ler_janelas`)."""
    from frontend.db_readers.comercial import dia_da_live  # noqa: PLC0415
    from frontend.services.comercial.regras import janela_reativa  # noqa: PLC0415
    from frontend.services.comercial.telas import mes_do_codigo  # noqa: PLC0415
    saida = []
    for lanc, evento, aulas, _hm, _tm in lancamentos:
        dia = dia_da_live(evento, aulas)
        auto = janela_reativa(str(lanc), dia, (), ()) if dia else None
        auto = (auto.inicio, auto.fim) if auto else None
        manual = manuais.get(str(lanc))
        saida.append({"lancamento": str(lanc), "live": dia, "auto": auto, "manual": manual,
                      "vigor": (manual["inicio"], manual["fim"]) if manual else auto,
                      "mes": mes_do_codigo(str(lanc))})
    return sorted(saida, key=lambda j: (j["mes"] is None, -(j["mes"].toordinal() if j["mes"] else 0),
                                        j["lancamento"]))


def view_regras(dados: dict, hoje: date, mes_meta: date, q_base: str | None = None,
                q_oferta: str | None = None) -> dict:
    from frontend.services.comercial.tabelas import BASE_TMB_POR_CATEGORIA  # noqa: PLC0415
    vendedores = sorted(dados["vendedores"], key=lambda v: _num_codigo(v["codigo"]))
    bases, bases_total = filtrar_bases(dados["bases"], q_base)
    ofertas, ofertas_total = filtrar_ofertas(dados["ofertas"], q_oferta)
    metas = dados.get("metas") or {}
    return {
        "hoje": hoje, "inicio_padrao": hoje.replace(day=1), "encerrar_padrao": proximo_mes(hoje),
        "mes_meta": mes_meta,
        "mes_meta_txt": f"{mes_meta:%Y-%m}",
        "meses_meta": _opcoes_mes_meta(hoje),
        "vendedores": vendedores,
        "vendedores_ativos": [v for v in vendedores if v["ativo"]],
        "acessos": dados["acessos"],
        "regras": grupos_regras(dados["regras"]),
        "participacoes": grupos_participacoes(dados["participacoes"]),
        "bases": bases, "bases_total": bases_total, "bases_cadastradas": len(dados["bases"]),
        "q_base": (q_base or "").strip()[:64],
        "ofertas": ofertas, "ofertas_total": ofertas_total, "q_oferta": (q_oferta or "").strip()[:64],
        "categorias": sorted(set(dados["categorias"]) | set(BASE_TMB_POR_CATEGORIA)),
        "janelas": linhas_janelas(dados["lancamentos"], dados["janelas"]),
        "metas": [{"codigo": v["codigo"], "nome": v["nome"], "meta": (metas.get(v["codigo"]) or {}).get("valor")}
                  for v in vendedores if v["ativo"] or v["codigo"] in metas],
        "historico": dados["historico"],
        "plataformas": PLATAFORMAS, "modalidades": MODALIDADES, "tipos": TIPOS, "niveis": NIVEIS,
        "limite": LIMITE_LISTA,
    }


def _opcoes_mes_meta(hoje: date) -> list[tuple[str, str]]:
    from frontend.services.comercial.telas import _periodo_mes  # noqa: PLC0415
    m, saida = soma_meses(hoje.replace(day=1), 1), []
    while m >= INICIO_MINIMO and len(saida) < 13:
        saida.append((f"{m:%Y-%m}", _periodo_mes(m).rotulo))
        m = soma_meses(m, -1)
    return saida
