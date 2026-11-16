"""
frontend/services/monitor_boas_vindas.py — Monitor da automação de boas-vindas no
dia de abertura do carrinho (página /boas-vindas).

Compara, de 5 em 5 minutos, quem comprou a Mentoria Vitalícia do lançamento com
quem entrou na automação "Email Boas Vindas EDM" do Active Campaign. Nasceu como
monitor ao vivo no carrinho do PES-NOV-26 (12/11/26), quando 61 alunos novos
ficaram sem o e-mail porque a integração de fora do Active não colocou a tag que
dispara a automação. Regras que saíram dali, todas em config/monitor_boas_vindas.yaml
ou aqui:

- o gatilho da automação é a tag [MENT] [VIT] <curso> adicionada (roda 1x por contato);
- quem já comprou antes (Hotmart/TMB aprovada antes do dia) não recebe boas-vindas,
  e isso está certo: conta como "já era aluno", não como falha. Ter só a tag
  EDM_LEAD não faz de ninguém aluno;
- compra com menos de `tolerancia_min` minutos ainda pode estar a caminho;
- a API do Active NÃO devolve contactAutomations em ordem cronológica: sempre
  pedir orders[adddate]=DESC.

Só leitura: GET na API do Active, SELECT no banco operacional. Roda sozinho só no
dia de abertura (launch_config.abertura_oficial_carrinho, senão carrinho_start_date);
nos outros dias o laço só confere a data. A série da fila ("na fila" a cada leitura)
fica em memória: um redeploy no meio do dia perde os pontos anteriores da fila,
mas as curvas de compra e entrada são refeitas pelos horários e não se perdem.
"""
from __future__ import annotations

import asyncio
import os
import re
import threading
import time
from datetime import date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml
from sqlalchemy import text

from logger import get_logger

logger = get_logger("frontend")

BR = ZoneInfo("America/Sao_Paulo")
_CFG_PATH = Path(__file__).resolve().parents[2] / "config" / "monitor_boas_vindas.yaml"
_EMAILS_TESTE = ("+teste", "@aprovasim.com")


# ── Config ─────────────────────────────────────────────────────────────────────

def config() -> dict:
    with open(_CFG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ── Funções puras (testadas em tests/test_monitor_boas_vindas.py) ─────────────

def parse_hm(valor) -> datetime | None:
    """Data da Hotmart em qualquer dos 3 formatos que a tabela mistura (epoch em
    s ou ms, DD/MM/AAAA[ HH:MM[:SS]], ISO), sempre no fuso de Brasília."""
    s = str(valor or "").strip()
    if not s:
        return None
    if s.isdigit():
        n = int(s)
        if len(s) == 13:
            n //= 1000
        return datetime.fromtimestamp(n, BR)
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?", s)
    if m:
        d, mo, y, hh, mi, ss = m.groups()
        return datetime(int(y), int(mo), int(d), int(hh or 0), int(mi or 0), int(ss or 0), tzinfo=BR)
    try:
        x = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return x.astimezone(BR) if x.tzinfo else x.replace(tzinfo=BR)


def _piso(x: datetime, bucket_min: int) -> datetime:
    return x - timedelta(minutes=x.minute % bucket_min, seconds=x.second, microseconds=x.microsecond)


def chave_bucket(agora: datetime, bucket_min: int = 5) -> str:
    """Fim do bloco de `bucket_min` em que `agora` cai: é onde a foto da fila entra na série."""
    return (_piso(agora, bucket_min) + timedelta(minutes=bucket_min)).isoformat(timespec="minutes")


def montar_serie(inicio: datetime, agora: datetime, tempos_compra: list[datetime],
                 tempos_entrada: list[datetime], fila_hist: dict[str, int],
                 bucket_min: int = 5) -> list[dict]:
    """Um ponto a cada `bucket_min` minutos, com o acumulado ATÉ aquele horário.

    Começa no bloco da primeira compra ou entrada (não às 00:00, pra não desenhar
    horas de linha zerada) e vai até o bloco que contém `agora`."""
    bucket = timedelta(minutes=bucket_min)
    fim_atual = _piso(agora, bucket_min) + bucket
    primeiro = min([*sorted(tempos_compra)[:1], *sorted(tempos_entrada)[:1]], default=agora)
    t = max(_piso(inicio, bucket_min) + bucket, _piso(primeiro, bucket_min))
    compras, entradas = sorted(tempos_compra), sorted(tempos_entrada)
    serie = []
    while t <= fim_atual:
        k = t.isoformat(timespec="minutes")
        serie.append({
            "t": k,
            "rotulo": t.astimezone(BR).strftime("%H:%M"),
            "compradores": sum(1 for x in compras if x < t),
            "entradas": sum(1 for x in entradas if x < t),
            "fila": fila_hist.get(k),
        })
        t += bucket
    return serie


def classificar(compras: dict[str, tuple[datetime, str]], na_automacao: set[str],
                comprou_antes: set[str], agora: datetime, tolerancia_min: int) -> dict:
    """Separa quem comprou e NÃO está na automação em três grupos:
    já era aluno (certo ficar de fora), a caminho (comprou há menos da tolerância)
    e faltando (aluno novo, comprou há mais da tolerância: esse é o problema)."""
    limite = agora - timedelta(minutes=tolerancia_min)
    faltando, a_caminho, ja_alunos = [], 0, 0
    for email, (quando, produto) in compras.items():
        if email in na_automacao:
            continue
        if email in comprou_antes:
            ja_alunos += 1
        elif quando <= limite:
            faltando.append({"email": email, "quando": quando, "hora": quando.strftime("%H:%M"), "produto": produto})
        else:
            a_caminho += 1
    faltando.sort(key=lambda r: r["quando"])
    return {"faltando": faltando, "a_caminho": a_caminho, "ja_alunos": ja_alunos}


def linha_para_abertura(row: dict, por_projeto: dict) -> dict | None:
    """Linha do launch_config -> abertura monitorável, ou None se o lançamento não
    usa esta automação (prefixo fora de por_projeto) ou não tem data/produto."""
    codigo = str(row.get("lancamento_codigo") or "").upper()
    prefixo = codigo.split("-")[0]
    proj = por_projeto.get(prefixo)
    dia = row.get("abertura_oficial_carrinho") or row.get("carrinho_start_date")
    if not proj or not dia:
        return None
    if isinstance(dia, str):
        dia = date.fromisoformat(dia[:10])
    produtos = [str(p) for p in (row.get("hotmart_produto_ids") or []) if str(p).strip().isdigit()]
    if not produtos:
        return None
    return {
        "codigo": codigo, "prefixo": prefixo, "dia": dia,
        "hora": row.get("abertura_oficial_hora") or None,
        "produtos": produtos, **proj,
    }


# ── Leitura: launch_config ─────────────────────────────────────────────────────

_ABERTURAS: dict = {"em": 0.0, "lista": []}
_ABERTURAS_TTL_S = 600


def aberturas() -> list[dict]:
    """Todas as aberturas monitoráveis, da mais antiga pra mais nova (cache de 10 min)."""
    if time.monotonic() - _ABERTURAS["em"] < _ABERTURAS_TTL_S and _ABERTURAS["lista"]:
        return _ABERTURAS["lista"]
    from frontend.db import _get_users_engine  # noqa: PLC0415

    por_projeto = config().get("por_projeto") or {}
    with _get_users_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT lancamento_codigo, abertura_oficial_carrinho, carrinho_start_date, "
            "abertura_oficial_hora, hotmart_produto_ids FROM launch_config"
        )).mappings().all()
    lista = [a for a in (linha_para_abertura(dict(r), por_projeto) for r in rows) if a]
    lista.sort(key=lambda a: (a["dia"], a["codigo"]))
    _ABERTURAS.update(em=time.monotonic(), lista=lista)
    return lista


def abertura_do_dia(dia: date) -> dict | None:
    return next((a for a in aberturas() if a["dia"] == dia), None)


# ── Leitura: Active Campaign ───────────────────────────────────────────────────

class _Active:
    def __init__(self):
        self.base = os.environ["AC_API_URL"].rstrip("/") + "/api/3"
        self.s = requests.Session()
        self.s.headers.update({"Api-Token": os.environ["AC_API_KEY"]})

    def get(self, caminho: str, **params) -> dict:
        for tentativa in range(4):
            r = self.s.get(f"{self.base}/{caminho}", params=params, timeout=60)
            if r.status_code == 429:  # limite de 5 req/s da conta, dividido com o ETL e a integração
                time.sleep(2 + 2 * tentativa)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"Active Campaign: 429 persistente em {caminho}")


_EMAIL_DO_CONTATO: dict[str, str] = {}   # id do contato no Active -> e-mail (não muda; vale o processo todo)


def _entradas_automacao(ac: _Active, automacao_id: str, desde: datetime) -> list[dict]:
    """Entradas na automação desde `desde`, da mais nova pra mais velha."""
    vistos: dict[str, dict] = {}
    off = 0
    while True:
        pg = ac.get(f"automations/{automacao_id}/contactAutomations",
                    limit=100, offset=off, **{"orders[adddate]": "DESC"}).get("contactAutomations", [])
        for x in pg:
            vistos[x["id"]] = x
        mais_velha = min((datetime.fromisoformat(x["adddate"]) for x in pg), default=desde)
        if len(pg) < 100 or mais_velha < desde or off > 20000:
            break
        off += 100
    linhas = list(vistos.values())
    faltam = sorted({x["contact"] for x in linhas} - set(_EMAIL_DO_CONTATO))
    for i in range(0, len(faltam), 100):
        for c in ac.get("contacts", ids=",".join(faltam[i:i + 100]), limit=100).get("contacts", []):
            _EMAIL_DO_CONTATO[c["id"]] = (c.get("email") or "").strip().lower()
    for x in linhas:
        x["_quando"] = datetime.fromisoformat(x["adddate"]).astimezone(BR)
        x["_email"] = _EMAIL_DO_CONTATO.get(x["contact"])
    return linhas


# ── Leitura: vendas (banco operacional) ────────────────────────────────────────

def _compras(ab: dict, inicio: datetime, fim: datetime) -> dict[str, tuple[datetime, str]]:
    """E-mail -> (hora da aprovação, produto) da primeira compra do dia, Hotmart + TMB."""
    from frontend.db import _get_users_engine  # noqa: PLC0415
    from frontend.db_readers._vendas_comum import _hm_data_sql  # noqa: PLC0415

    d_sql = f"COALESCE({_hm_data_sql('data_da_transacao')}, {_hm_data_sql('confirmacao_do_pagamento')})"
    with _get_users_engine().connect() as conn:
        hm = conn.execute(text(f"""
            SELECT lower(trim(email_do_a_comprador_a)) AS email, produto,
                   data_da_transacao, confirmacao_do_pagamento
            FROM hotmart_clean_oficial
            WHERE codigo_do_produto::text = ANY(:ids)
              AND {d_sql} BETWEEN :d0 AND :d1
        """), {"ids": ab["produtos"], "d0": inicio.date() - timedelta(days=1), "d1": inicio.date()}).mappings().all()
        tmb = conn.execute(text("""
            SELECT lower(trim(email_cliente)) AS email, produto, data_efetivado
            FROM tmb_clean_oficial
            WHERE produto ILIKE :p AND data_efetivado >= :d0 AND data_efetivado < :d1
        """), {"p": ab["tmb_produto_like"], "d0": inicio.replace(tzinfo=None),
               "d1": fim.replace(tzinfo=None)}).mappings().all()

    compras: dict[str, tuple[datetime, str]] = {}

    def _guardar(email, quando, produto):
        if not email or any(t in email for t in _EMAILS_TESTE) or not quando:
            return
        if not (inicio <= quando < fim):
            return
        if email not in compras or quando < compras[email][0]:
            compras[email] = (quando, produto)

    for r in hm:
        # Aprovação primeiro: é quando a Hotmart manda a tag pro Active.
        _guardar(r["email"], parse_hm(r["confirmacao_do_pagamento"]) or parse_hm(r["data_da_transacao"]),
                 (r["produto"] or "").strip())
    for r in tmb:
        q = r["data_efetivado"]
        if q is not None:
            q = q.replace(tzinfo=BR) if q.tzinfo is None else q.astimezone(BR)
        _guardar(r["email"], q, f"{(r['produto'] or '').strip()} · TMB")
    return compras


def _comprou_antes(emails: list[str], inicio: datetime) -> set[str]:
    """Quem já tinha compra aprovada (qualquer produto) antes do dia: já é aluno."""
    if not emails:
        return set()
    from frontend.db import _get_users_engine  # noqa: PLC0415
    from frontend.db_readers._vendas_comum import _hm_data_sql  # noqa: PLC0415

    d_sql = f"COALESCE({_hm_data_sql('data_da_transacao')}, {_hm_data_sql('confirmacao_do_pagamento')})"
    with _get_users_engine().connect() as conn:
        antes = {r[0] for r in conn.execute(text(f"""
            SELECT DISTINCT lower(trim(email_do_a_comprador_a)) FROM hotmart_clean_oficial
            WHERE lower(trim(email_do_a_comprador_a)) = ANY(:e) AND {d_sql} < :d0
        """), {"e": emails, "d0": inicio.date()})}
        antes |= {r[0] for r in conn.execute(text("""
            SELECT DISTINCT lower(trim(email_cliente)) FROM tmb_clean_oficial
            WHERE lower(trim(email_cliente)) = ANY(:e) AND data_efetivado < :d0
        """), {"e": emails, "d0": inicio.replace(tzinfo=None)})}
    return antes


# ── Cálculo ────────────────────────────────────────────────────────────────────

_FILA: dict[tuple[str, str], dict[str, int]] = {}   # (lançamento, dia) -> {fim do bloco: na fila}


def calcular(ab: dict, agora: datetime | None = None) -> dict:
    """Retrato do dia de abertura de `ab` até `agora` (ou até o fim do dia, se já passou)."""
    cfg = config()
    bucket = int(cfg.get("intervalo_min") or 5)
    tolerancia = int(cfg.get("tolerancia_min") or 15)
    inicio = datetime.combine(ab["dia"], dtime(0), BR)
    fim = inicio + timedelta(days=1)
    agora_real = agora or datetime.now(BR)
    agora = min(agora_real, fim - timedelta(seconds=1))
    ao_vivo = inicio <= agora_real < fim

    linhas = _entradas_automacao(_Active(), str(cfg["automacao_id"]), inicio - timedelta(days=1))
    compras = _compras(ab, inicio, fim)
    compras = {e: v for e, v in compras.items() if v[0] <= agora}

    na_automacao = {x["_email"] for x in linhas if x["_email"]}
    fora = [e for e in compras if e not in na_automacao]
    grupos = classificar(compras, na_automacao, _comprou_antes(fora, inicio), agora, tolerancia)

    # Entradas e fila contam só os compradores deste lançamento: a automação é a
    # mesma dos três cursos, e quem comprou outro curso no dia não entra na conta.
    entrou: dict[str, datetime] = {}
    na_fila: set[str] = set()
    outras: set[str] = set()
    for x in linhas:
        e = x["_email"]
        if not e:
            continue
        if e in compras:
            if x["_quando"] >= inicio:
                entrou[e] = min(entrou.get(e, x["_quando"]), x["_quando"])
            if str(x.get("status")) == "1":
                na_fila.add(e)
        elif inicio <= x["_quando"] <= agora:
            outras.add(e)

    hist = _FILA.setdefault((ab["codigo"], ab["dia"].isoformat()), {})
    if ao_vivo:
        hist[chave_bucket(agora, bucket)] = len(na_fila)

    por_produto: dict[str, dict] = {}
    for e, (_, produto) in compras.items():
        r = por_produto.setdefault(produto, {"produto": produto, "compradores": 0, "na_automacao": 0})
        r["compradores"] += 1
        r["na_automacao"] += e in na_automacao

    return {
        "codigo": ab["codigo"], "curso": ab.get("curso"), "dia": ab["dia"],
        "tag_gatilho": ab.get("tag_gatilho"),
        "automacao_id": str(cfg["automacao_id"]), "automacao_nome": cfg.get("automacao_nome"),
        "atualizado_em": agora_real, "ao_vivo": ao_vivo, "tolerancia_min": tolerancia, "intervalo_min": bucket,
        "compradores": len(compras),
        "entradas": len(entrou),
        "fila": len(na_fila),
        "faltando": grupos["faltando"],
        "a_caminho": grupos["a_caminho"],
        "ja_alunos": grupos["ja_alunos"],
        "outras_entradas": len(outras),
        "por_produto": sorted(por_produto.values(), key=lambda r: -r["compradores"]),
        "serie": montar_serie(inicio, agora, [v[0] for v in compras.values()], list(entrou.values()), hist, bucket),
    }


# ── Cache + laço de fundo ──────────────────────────────────────────────────────

_ULTIMO: dict[str, tuple[float, dict]] = {}
_TRAVA = threading.Lock()
ESTADO: dict = {"ultima_rodada": None, "erro": None}


def obter(ab: dict, max_idade_s: int = 270) -> dict:
    """Retrato em cache (até `max_idade_s`) ou recém-calculado. Uma conta por vez:
    duas abas abertas não dobram as chamadas ao Active."""
    chave = f"{ab['codigo']}|{ab['dia']}"
    with _TRAVA:
        em, snap = _ULTIMO.get(chave, (0.0, None))
        if snap is not None and time.monotonic() - em < max_idade_s:
            return snap
        snap = calcular(ab)
        _ULTIMO[chave] = (time.monotonic(), snap)
        return snap


def rodada(hoje: date | None = None) -> dict | None:
    """Uma leitura do laço. Só calcula se algum carrinho abre hoje."""
    hoje = hoje or datetime.now(BR).date()
    ab = abertura_do_dia(hoje)
    if not ab:
        return None
    snap = obter(ab, max_idade_s=60)
    ESTADO.update(ultima_rodada=datetime.now(BR), erro=None)
    return snap


async def _laco() -> None:
    await asyncio.sleep(60)
    while True:
        try:
            await asyncio.to_thread(rodada)
        except Exception as e:  # noqa: BLE001
            ESTADO["erro"] = str(e)[:300]
            logger.exception("Monitor de boas-vindas: rodada falhou")
        await asyncio.sleep(int(config().get("intervalo_min") or 5) * 60)


_TAREFA: asyncio.Task | None = None


def agendar() -> None:
    """Chamado no startup do site. Uma tarefa só por processo; MONITOR_BOAS_VINDAS=false desliga."""
    global _TAREFA
    if os.environ.get("MONITOR_BOAS_VINDAS", "true").lower() != "true":
        logger.info("Monitor de boas-vindas desligado (MONITOR_BOAS_VINDAS=false)")
        return
    if not (os.environ.get("AC_API_URL") and os.environ.get("AC_API_KEY")):
        logger.warning("Monitor de boas-vindas: AC_API_URL/AC_API_KEY ausentes; não vai rodar")
        return
    if _TAREFA is not None and not _TAREFA.done():
        return
    _TAREFA = asyncio.create_task(_laco())
    logger.info("Monitor de boas-vindas agendado: só calcula no dia de abertura do carrinho")
