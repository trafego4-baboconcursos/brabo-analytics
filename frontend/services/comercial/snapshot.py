"""Snapshot do mês: cache do cálculo da comissão (Task 4).

`calcular_mes` lê cadastros + vendas + janelas e roda o motor (~13 s por mês); `obter_mes`
devolve o snapshot gravado em `comercial_snapshot` quando está em dia, senão recalcula e grava.
Toda escrita em cadastro chama `marcar_desatualizado`. O store é injetável para testes.
"""
from __future__ import annotations

import decimal
import json
from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import text

from logger import get_logger
from frontend.services.comercial.calculo import LinhaComissao, calcular
from frontend.services.comercial.meses import ultimo_dia

logger = get_logger("db")
_SP = ZoneInfo("America/Sao_Paulo")


@dataclass
class ResultadoMes:
    mes: date
    linhas: list[LinhaComissao]
    sem_data: list  # [(lançamento, produtos hotmart, produtos tmb)]
    gerado_em: datetime
    desatualizado: bool = False
    # Task 7b: mês fechado = linhas congeladas (nunca recalculadas) + bônus congelado
    fechado: bool = False
    fechado_em: datetime | None = None
    fechado_por: str | None = None
    bonus: dict | None = None
    totais: dict | None = None


# ---------------------------------------------------------------- serialização
_DEC = {f.name for f in fields(LinhaComissao) if "Decimal" in str(f.type)}


def linha_para_json(l: LinhaComissao) -> dict:
    d: dict = {}
    for f in fields(LinhaComissao):
        v = getattr(l, f.name)
        if isinstance(v, Decimal):
            v = str(v)
        elif isinstance(v, datetime):
            v = v.isoformat()
        d[f.name] = v
    return d


def linha_de_json(d: dict) -> LinhaComissao:
    kw = dict(d)
    for k in _DEC:
        if kw.get(k) is not None:  # campo com default ausente em snapshot antigo: fica o default
            kw[k] = Decimal(kw[k])
    kw["data"] = datetime.fromisoformat(kw["data"])
    return LinhaComissao(**kw)


def linhas_para_json(linhas: list[LinhaComissao]) -> str:
    return json.dumps([linha_para_json(l) for l in linhas], ensure_ascii=False)


def linhas_de_json(txt: str | list) -> list[LinhaComissao]:
    dados = json.loads(txt) if isinstance(txt, (str, bytes)) else txt
    return [linha_de_json(d) for d in dados]


def alertas_para_json(sem_data: list) -> str:
    return json.dumps([[a, sorted(b), sorted(c)] for a, b, c in sem_data], ensure_ascii=False)


def alertas_de_json(txt: str | list) -> list:
    dados = json.loads(txt) if isinstance(txt, (str, bytes)) else txt
    return [(a, frozenset(b), frozenset(c)) for a, b, c in dados]


# ---------------------------------------------------------------- cálculo
def calcular_mes(mes: date, hoje: datetime) -> ResultadoMes:
    """Cadastros do banco + vendas do mês + janelas -> linhas. `hoje`: agora em SP."""
    from frontend.db_readers.comercial import ler_cadastros, ler_janelas, ler_vendas  # noqa: PLC0415

    from frontend.services.comercial import fechamento as fech  # noqa: PLC0415

    ini, fim = mes.replace(day=1), ultimo_dia(mes)
    cad = ler_cadastros()
    extra = frozenset(cad.atribuicoes)
    # Ruling 17/20: o que os meses fechados logo antes deste ainda devem a ele (estorno e
    # venda tardia), só dentro do horizonte (+ decisões "tira")
    tira = {t for t, d in cad.decisoes_reembolso.items() if d == "tira"}
    pend = fech.ler_pendentes(ini, hoje, tira)
    if pend is None:
        vendas = ler_vendas(ini, fim, transacoes_extra=extra, ofertas=cad.ofertas)
        janelas, sem_data = ler_janelas(ini, fim)
        return ResultadoMes(ini, calcular(vendas, cad, janelas, hoje), sem_data, agora_sp())
    desde = pend.recentes[0] if pend.recentes else ini
    alvo = frozenset(l.transacao for _c, l in pend.cands)
    todas = ler_vendas(desde, fim, transacoes_extra=extra | alvo, ofertas=cad.ofertas,
                       incluir_extra_fora_do_periodo=True)
    vendas = [v for v in todas if ini <= v.data.date() <= fim]
    recentes = set(pend.recentes)
    tardias = [v for v in todas if v.data.date().replace(day=1) in recentes
               and v.transacao not in pend.ja_congeladas]
    janelas, sem_data = ler_janelas(ini, fim)
    linhas = calcular(vendas, cad, janelas, hoje)
    if tardias:
        janelas_t, _ = ler_janelas(desde, ini - timedelta(days=1))
        linhas += fech.marcar_tardias(calcular(tardias, cad, janelas_t, hoje))
    atuais = {v.transacao: v for v in todas if v.transacao in alvo}
    linhas += fech.estornos(pend.cands, atuais, cad.decisoes_reembolso, hoje)
    # Ruling 22: reembolso a verificar de venda congelada -> pendência (valor 0) que bloqueia fechar
    linhas += fech.a_verificar_de_fechados(pend.cands, atuais, cad.decisoes_reembolso, hoje)
    return ResultadoMes(ini, linhas, sem_data, agora_sp())  # gerado_em = hora real, não `hoje`


# ---------------------------------------------------------------- store
class Store(Protocol):
    def fechamento(self, mes: date) -> ResultadoMes | None: ...
    def get(self, mes: date) -> ResultadoMes | None: ...
    def put(self, r: ResultadoMes, calculo_inicio: datetime) -> None: ...
    def inicio_calculo(self) -> datetime: ...
    def marcar_desatualizado(self, mes: date | None) -> None: ...


class StoreBanco:
    """Snapshot em `comercial_snapshot` (banco operacional). Tabela ausente = sem snapshot."""

    def fechamento(self, mes: date) -> ResultadoMes | None:
        """Mês fechado (ativo) -> linhas congeladas. Congelado ilegível ESTOURA: um mês fechado
        nunca é recalculado em silêncio."""
        from frontend.db_readers.comercial import ler_fechamento  # noqa: PLC0415
        return resultado_fechado(mes, ler_fechamento(mes))

    def get(self, mes: date) -> ResultadoMes | None:
        from frontend.db import _get_users_engine  # noqa: PLC0415
        from frontend.db_readers.comercial import tabela_comercial_ausente  # noqa: PLC0415
        try:
            with _get_users_engine().connect() as c:
                row = c.execute(text(
                    "SELECT gerado_em, linhas, alertas, desatualizado FROM comercial_snapshot "
                    "WHERE mes = :mes"), {"mes": mes.replace(day=1)}).fetchone()
        except Exception as exc:
            if tabela_comercial_ausente(exc):
                return None
            raise
        if row is None:
            return None
        gerado, linhas, alertas, desat = row
        try:
            ls, al = linhas_de_json(linhas), alertas_de_json(alertas)
        except (TypeError, KeyError, ValueError, decimal.InvalidOperation):
            logger.warning("comercial: snapshot de %s ilegível (formato mudou?); recalculando", mes)
            return None
        if gerado.tzinfo is not None:  # timestamptz volta com fuso; o resto do módulo usa SP naive
            gerado = gerado.astimezone(_SP).replace(tzinfo=None)
        return ResultadoMes(mes.replace(day=1), ls, al, gerado, bool(desat))

    def inicio_calculo(self) -> datetime:
        """Relógio do BANCO (o mesmo que carimba invalidado_em), sem depender do desvio local."""
        from frontend.db import _get_users_engine  # noqa: PLC0415
        with _get_users_engine().connect() as c:
            return c.execute(text("SELECT now()")).scalar_one()

    def put(self, r: ResultadoMes, calculo_inicio: datetime) -> None:
        from frontend.db import _get_users_engine  # noqa: PLC0415
        from frontend.db_readers.comercial import SQL_SNAPSHOT_UPSERT, exigir_so_comercial  # noqa: PLC0415
        exigir_so_comercial(SQL_SNAPSHOT_UPSERT)
        with _get_users_engine().begin() as c:
            c.execute(text(SQL_SNAPSHOT_UPSERT),
                      {"mes": r.mes, "gerado_em": r.gerado_em.replace(tzinfo=_SP) if r.gerado_em.tzinfo is None else r.gerado_em, "linhas": linhas_para_json(r.linhas),
                       "alertas": alertas_para_json(r.sem_data), "calculo_inicio": calculo_inicio})

    def marcar_desatualizado(self, mes: date | None) -> None:
        from frontend.db import _get_users_engine  # noqa: PLC0415
        from frontend.db_readers import comercial as com  # noqa: PLC0415
        sql = com.SQL_SNAPSHOT_DESATUALIZAR_TODOS if mes is None else com.SQL_SNAPSHOT_DESATUALIZAR_MES
        com.exigir_so_comercial(sql)
        with _get_users_engine().begin() as c:
            c.execute(text(sql), {} if mes is None else {"mes": mes.replace(day=1)})


def resultado_fechado(mes: date, f: dict | None) -> ResultadoMes | None:
    """Linha de comercial_fechamentos -> ResultadoMes congelado (None se não há ou foi reaberto)."""
    from frontend.services.comercial.fechamento import bonus_de_json  # noqa: PLC0415
    if not f or not f.get("ativo"):
        return None
    tot = f.get("totais")
    tot = json.loads(tot) if isinstance(tot, (str, bytes)) else tot
    return ResultadoMes(mes.replace(day=1), linhas_de_json(f["linhas"]), [], f["fechado_em"],
                        fechado=True, fechado_em=f["fechado_em"], fechado_por=f["fechado_por"],
                        bonus=bonus_de_json(f.get("bonus")), totais=tot)


def agora_sp() -> datetime:
    return datetime.now(_SP).replace(tzinfo=None)


# ---------------------------------------------------------------- cache em memória (Desempenho)
# O Desempenho lê o ano inteiro (11+ meses, ~30 mil linhas); cada mês custava ~2 s de banco
# (10/11/26: ~23 s a página). O resultado decodificado fica na memória do processo, preso à
# "versão" do mês (gerado_em/desatualizado/invalidado_em do snapshot + ativo/fechado_em/
# reaberto_em do fechamento), lida numa consulta leve, sem o jsonb. Mudou a versão -> relê.
# Só com o StoreBanco padrão: store injetado (testes) não usa o cache.
SQL_VERSOES_SNAPSHOT = ("SELECT mes, gerado_em, desatualizado, invalidado_em "
                        "FROM comercial_snapshot")
SQL_VERSOES_FECHAMENTO = "SELECT mes, ativo, fechado_em, reaberto_em FROM comercial_fechamentos"
_CACHE_MAX = 24
_cache: dict[date, tuple[tuple, ResultadoMes]] = {}
_cache_lock = __import__("threading").Lock()


def versoes_guardadas() -> dict[date, tuple] | None:
    """{mês: (snapshot, fechamento)} com as colunas de versão; None se não deu para ler."""
    from frontend.db import _get_users_engine  # noqa: PLC0415
    try:
        with _get_users_engine().connect() as c:
            snaps = {r[0]: tuple(r[1:]) for r in c.execute(text(SQL_VERSOES_SNAPSHOT)).fetchall()}
            fechs = {r[0]: tuple(r[1:]) for r in c.execute(text(SQL_VERSOES_FECHAMENTO)).fetchall()}
    except Exception:  # noqa: BLE001 — sem versão, lê do jeito antigo (sem cache)
        logger.warning("versoes_guardadas: sem leitura de versão; segue sem cache", exc_info=True)
        return None
    return {m: (snaps.get(m), fechs.get(m)) for m in set(snaps) | set(fechs)}


def _do_cache(mes: date, versao: tuple | None) -> ResultadoMes | None:
    if versao is None:
        return None
    with _cache_lock:
        hit = _cache.get(mes)
    return hit[1] if hit and hit[0] == versao else None


def _para_cache(mes: date, versao: tuple | None, r: ResultadoMes | None) -> None:
    if versao is None or r is None:
        return
    with _cache_lock:
        _cache[mes] = (versao, r)
        while len(_cache) > _CACHE_MAX:
            _cache.pop(min(_cache))


def limpar_cache() -> None:
    with _cache_lock:
        _cache.clear()


# ---------------------------------------------------------------- reivindicação ágil (25/11/26)
# Rafael: reivindicar e aprovar demoravam 10–30 s. Causas medidas: (1) cada aprovação marcava o
# mês para recalcular e a página seguinte refazia o mês inteiro na hora (~12 s); (2) achar UMA
# venda baixava o snapshot inteiro do mês (2,5–4 s); (3) a busca por telefone baixava o mês
# anterior inteiro. Daqui para baixo: leitura só das linhas pedidas, a tela de Inconsistências
# servida da memória (mesmo desatualizada) e o recálculo em segundo plano, um por mês.
SQL_LINHAS_SNAP = (
    "SELECT e.linha FROM comercial_snapshot s CROSS JOIN LATERAL jsonb_array_elements(s.linhas) "
    "AS e(linha) WHERE s.mes = :mes AND e.linha->>'transacao' = ANY(:transacoes)")
SQL_LINHAS_FECH = (
    "SELECT e.linha FROM comercial_fechamentos f CROSS JOIN LATERAL jsonb_array_elements(f.linhas) "
    "AS e(linha) WHERE f.ativo AND f.mes = :mes AND e.linha->>'transacao' = ANY(:transacoes)")
SQL_FECH_ATIVO_DO_MES = "SELECT 1 FROM comercial_fechamentos WHERE ativo AND mes = :mes"
SQL_CANDIDATAS_SNAP = (
    "SELECT DISTINCT e.linha->>'transacao' FROM comercial_snapshot s CROSS JOIN LATERAL "
    "jsonb_array_elements(s.linhas) AS e(linha) WHERE s.mes = :mes AND ("
    "(e.linha->>'papel' = 'venda' AND e.linha->>'situacao' = 'inconsistente' "
    "AND e.linha->>'motivo' = 'sem_codigo') "
    "OR (e.linha->>'papel' = 'ia' AND e.linha->>'situacao' <> 'cancelada'))")


def linhas_das_transacoes(mes: date, transacoes: list[str]) -> list[LinhaComissao] | None:
    """Só as linhas destas transações no mês guardado (congelado, se o mês está fechado), sem
    baixar o mês inteiro. None = não deu para ler (quem chama cai no caminho antigo)."""
    from frontend.db import _get_users_engine  # noqa: PLC0415
    ts = sorted({t for t in transacoes if t})
    if mes is None or not ts:
        return []
    m = mes.replace(day=1)
    try:
        with _get_users_engine().connect() as c:
            fechado = c.execute(text(SQL_FECH_ATIVO_DO_MES), {"mes": m}).fetchone() is not None
            rows = c.execute(text(SQL_LINHAS_FECH if fechado else SQL_LINHAS_SNAP),
                             {"mes": m, "transacoes": ts}).fetchall()
        return [linha_de_json(r[0] if not isinstance(r[0], str) else json.loads(r[0])) for r in rows]
    except Exception:  # noqa: BLE001
        logger.warning("linhas_das_transacoes(%s): sem leitura direta; caminho antigo", mes, exc_info=True)
        return None


def transacoes_candidatas(mes: date) -> list[str] | None:
    """Transações reivindicáveis do snapshot guardado do mês (sem código / Camila), só os
    códigos. None = não deu para ler."""
    from frontend.db import _get_users_engine  # noqa: PLC0415
    try:
        with _get_users_engine().connect() as c:
            return [r[0] for r in c.execute(text(SQL_CANDIDATAS_SNAP), {"mes": mes.replace(day=1)}).fetchall()]
    except Exception:  # noqa: BLE001
        logger.warning("transacoes_candidatas(%s): sem leitura direta", mes, exc_info=True)
        return None


_bg_lock = __import__("threading").Lock()
_bg_estado: dict[date, str] = {}          # mês -> "rodando" | "de_novo"
_bg_fim: dict[date, object] = {}          # mês -> threading.Event do recálculo em andamento


def recalcular_em_segundo_plano(mes: date) -> bool:
    """Recalcula o mês numa thread. Um por mês: pedido durante o cálculo vira UMA rodada a mais
    no fim (aprovar 10 seguidas = 2 recálculos, não 10). Devolve False se só agendou a rodada."""
    import threading  # noqa: PLC0415
    m = mes.replace(day=1)
    with _bg_lock:
        if m in _bg_estado:
            _bg_estado[m] = "de_novo"
            return False
        _bg_estado[m] = "rodando"
        _bg_fim[m] = threading.Event()
    threading.Thread(target=_trabalho_segundo_plano, args=(m,), daemon=True,
                     name=f"comercial-recalculo-{m:%Y-%m}").start()
    return True


def _trabalho_segundo_plano(mes: date) -> None:
    try:
        while True:
            try:
                st = StoreBanco()
                if st.fechamento(mes) is None:  # mês fechado não se recalcula
                    _cache_depois_do_recalculo(mes, recalcular_mes(mes, store=st))
            except Exception:  # noqa: BLE001 — a próxima leitura recalcula do jeito normal
                logger.exception("comercial: recálculo em segundo plano de %s falhou", mes)
            with _bg_lock:
                if _bg_estado.get(mes) == "de_novo":
                    _bg_estado[mes] = "rodando"
                    continue
                return
    finally:
        with _bg_lock:
            _bg_estado.pop(mes, None)
            ev = _bg_fim.pop(mes, None)
        if ev is not None:
            ev.set()


def _cache_depois_do_recalculo(mes: date, r: ResultadoMes) -> None:
    """O recálculo acabou de gravar: guarda na memória com a versão nova, para a próxima tela
    não baixar o mês de novo (só se a versão do banco é a deste cálculo)."""
    versoes = versoes_guardadas()
    versao = (versoes or {}).get(mes)
    if versao and versao[0] and r.gerado_em == _naive_sp(versao[0][0]) and not versao[0][1]:
        _para_cache(mes, versao, r)


def aguardar_segundo_plano(mes: date, timeout: float = 90) -> None:
    """Se o mês está recalculando em segundo plano, espera (em vez de calcular de novo junto)."""
    with _bg_lock:
        ev = _bg_fim.get(mes.replace(day=1))
    if ev is not None:
        ev.wait(timeout)


def obter_mes_tela(mes: date, *, hoje: datetime | None = None) -> ResultadoMes:
    """Para a tela de Inconsistências/Reivindicações: o que está na memória, mesmo desatualizado
    (a ação acabou de marcar o mês), e o recálculo vai para o segundo plano. Sem nada na memória,
    o caminho normal (`obter_mes`)."""
    m = mes.replace(day=1)
    with _cache_lock:
        hit = _cache.get(m)
    if hit is None:
        return obter_mes(m, hoje=hoje)
    versao_mem, r = hit
    if r.fechado:
        return r
    versao = (versoes_guardadas() or {}).get(m)
    em_dia = (versao == versao_mem and not r.desatualizado
              and r.gerado_em.date() >= (hoje or agora_sp()).date())
    if not em_dia:
        recalcular_em_segundo_plano(m)
    return r


def obter_mes(mes: date, *, hoje: datetime | None = None, store: Store | None = None,
              versoes: dict[date, tuple] | None = None) -> ResultadoMes:
    """Mês fechado -> as linhas congeladas (comercial_fechamentos), nunca recalculadas. Senão,
    snapshot em dia se houver; senão calcula, grava e devolve. Com o store padrão, o que já
    foi lido e não mudou de versão sai da memória."""
    mes = mes.replace(day=1)
    if store is None:
        versoes = versoes if versoes is not None else versoes_guardadas()
        versao = (versoes or {}).get(mes) if versoes is not None else None
        r = _do_cache(mes, versao)
        if r is not None and (r.fechado or (not r.desatualizado
                                            and r.gerado_em.date() >= (hoje or agora_sp()).date())):
            return r
        with _bg_lock:
            rodando = mes in _bg_estado
        if rodando:  # o segundo plano já está refazendo este mês: espera e relê em vez de duplicar
            aguardar_segundo_plano(mes)
            versoes = versoes_guardadas()
            versao = (versoes or {}).get(mes) if versoes is not None else None
            r = _do_cache(mes, versao)
            if r is not None and (r.fechado or (not r.desatualizado
                                                and r.gerado_em.date() >= (hoje or agora_sp()).date())):
                return r
        r = _obter_mes_banco(mes, hoje=hoje, store=StoreBanco())
        # versão de antes da leitura: se o snapshot mudou no meio, a próxima leitura relê
        if r.fechado or (r.gerado_em and versao and versao[0] and r.gerado_em == _naive_sp(versao[0][0])):
            _para_cache(mes, versao, r)
        return r
    return _obter_mes_banco(mes, hoje=hoje, store=store)


def _naive_sp(dt):
    if isinstance(dt, datetime) and dt.tzinfo is not None:
        return dt.astimezone(_SP).replace(tzinfo=None)
    return dt


def _obter_mes_banco(mes: date, *, hoje: datetime | None, store: Store) -> ResultadoMes:
    congelado = store.fechamento(mes)
    if congelado is not None:
        return congelado
    r = store.get(mes)
    # `situacao` depende da data (prevista -> elegível): snapshot de dia anterior está velho
    if r is not None and not r.desatualizado and r.gerado_em.date() >= (hoje or agora_sp()).date():
        return r
    return recalcular_mes(mes, hoje=hoje, store=store)


def ler_guardado(mes: date, *, store: Store | None = None,
                 versoes: dict[date, tuple] | None = None) -> ResultadoMes | None:
    """O que estiver gravado para o mês, sem teste de frescor e sem gravar: snapshot velho ou
    desatualizado vale; mês fechado devolve o congelado; `None` se não há nada. Com o store
    padrão e `versoes` (de `versoes_guardadas`), usa o cache em memória."""
    mes = mes.replace(day=1)
    usa_cache = store is None and versoes is not None
    if usa_cache:
        versao = versoes.get(mes)
        if versao is None:
            return None  # nada gravado para o mês
        r = _do_cache(mes, versao)
        if r is not None:
            return r
    store = store or StoreBanco()
    congelado = store.fechamento(mes)
    r = congelado if congelado is not None else store.get(mes)
    if usa_cache:
        _para_cache(mes, versao, r)
    return r


def recalcular_mes(mes: date, *, hoje: datetime | None = None, store: Store | None = None) -> ResultadoMes:
    """Calcula e grava o snapshot (ignora o existente). Falha ao gravar não derruba o cálculo."""
    store = store or StoreBanco()
    try:
        inicio = store.inicio_calculo()  # antes de ler qualquer cadastro
    except Exception:
        logger.exception("comercial: sem relógio do banco para %s; não grava snapshot", mes)
        return calcular_mes(mes.replace(day=1), hoje or agora_sp())
    r = calcular_mes(mes.replace(day=1), hoje or agora_sp())
    try:
        store.put(r, inicio)
    except Exception:
        logger.exception("comercial: não gravou o snapshot de %s", mes)
    return r


def marcar_desatualizado(mes: date | None = None, *, store: Store | None = None) -> None:
    """Chamado por toda escrita em cadastro. None = todos os meses."""
    (store or StoreBanco()).marcar_desatualizado(mes.replace(day=1) if mes else None)
