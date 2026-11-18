"""
frontend/services/monitor_boas_vindas.py — Monitor da automação de boas-vindas no
carrinho, da abertura até o fechamento (página /boas-vindas).

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

Só leitura: GET na API do Active, SELECT no banco operacional. Roda sozinho do dia
de abertura (launch_config.abertura_oficial_carrinho, senão carrinho_start_date) até
o fim do carrinho (carrinho_end_date). Antes era só o dia de abertura; em 18/11/26
a Talita procurou uma aluna que pediu em 12/11 no parcelamento Hotmart e só foi
aprovada em 13/11, e ela não aparecia. Desde então entra quem fez o pedido OU teve
o pagamento aprovado dentro da janela (213 pedidos assim só no PES-NOV-26).
A série da fila ("na fila" a cada leitura) fica em memória: um redeploy perde os
pontos anteriores da fila, mas as curvas de compra e entrada são refeitas pelos
horários e não se perdem.
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


_PREFIXOS: set[str] | None = None


def tem_monitor(codigo: str | None) -> bool:
    """O lançamento usa esta automação? Só olha o prefixo (PES/PI/PBB), sem banco:
    é chamado pra montar o menu de toda página de lançamento."""
    global _PREFIXOS
    if _PREFIXOS is None:
        _PREFIXOS = {str(p).upper() for p in (config().get("por_projeto") or {})}
    return bool(codigo) and str(codigo).upper().split("-")[0] in _PREFIXOS


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


def hora_da_compra(pedido: datetime | None, aprovacao: datetime | None,
                   inicio: datetime, fim: datetime) -> datetime | None:
    """Hora que conta pra uma venda da Hotmart, ou None se ela está fora da janela.

    Entra quem fez o pedido OU teve a aprovação dentro de [inicio, fim): parcelamento
    Hotmart e boleto pedem num dia e aprovam no outro. A hora que conta é a da
    aprovação, porque é quando a Hotmart manda a tag pro Active."""
    dentro = [t for t in (pedido, aprovacao) if t and inicio <= t < fim]
    if not dentro:
        return None
    return aprovacao or pedido


def aberta_em(ab: dict, dia: date) -> bool:
    """O carrinho de `ab` está na janela do monitor nesse dia (abertura até o fim, inclusive)?"""
    return ab["dia"] <= dia <= ab["fim"]


def classificar(compras: dict[str, tuple[datetime, str]], na_automacao: set[str],
                comprou_antes: set[str], agora: datetime, tolerancia_min: int) -> dict:
    """Separa quem comprou e NÃO está na automação em três grupos:
    já era aluno (certo ficar de fora), a caminho (comprou há menos da tolerância)
    e faltando (aluno novo, comprou há mais da tolerância: esse é o problema)."""
    limite = agora - timedelta(minutes=tolerancia_min)
    faltando, a_caminho, ja_alunos = [], 0, 0
    situacao: dict[str, str] = {}
    for email, (quando, produto) in compras.items():
        if email in na_automacao:
            situacao[email] = "entrou"
        elif email in comprou_antes:
            situacao[email] = "ja_aluno"
            ja_alunos += 1
        elif quando <= limite:
            situacao[email] = "fora"
            faltando.append({"email": email, "quando": quando, "hora": quando.strftime("%H:%M"), "produto": produto})
        else:
            situacao[email] = "a_caminho"
            a_caminho += 1
    faltando.sort(key=lambda r: r["quando"])
    return {"faltando": faltando, "a_caminho": a_caminho, "ja_alunos": ja_alunos, "situacao": situacao}


SITUACOES = {
    "fora": "Fora da automação",
    "a_caminho": "A caminho",
    "entrou": "Entrou na automação",
    "ja_aluno": "Já era aluno",
}


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
    fim = row.get("carrinho_end_date")
    if isinstance(fim, str):
        fim = date.fromisoformat(fim[:10])
    if not fim or fim < dia:   # sem fim cadastrado: vale só o dia de abertura
        fim = dia
    return {
        "codigo": codigo, "prefixo": prefixo, "dia": dia, "fim": fim,
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
            "SELECT lancamento_codigo, abertura_oficial_carrinho, carrinho_start_date, carrinho_end_date, "
            "abertura_oficial_hora, hotmart_produto_ids FROM launch_config"
        )).mappings().all()
    lista = [a for a in (linha_para_abertura(dict(r), por_projeto) for r in rows) if a]
    lista.sort(key=lambda a: (a["dia"], a["codigo"]))
    _ABERTURAS.update(em=time.monotonic(), lista=lista)
    return lista


def abertas_em(dia: date) -> list[dict]:
    """Carrinhos na janela do monitor nesse dia. Pode ser mais de um: dois cursos com
    carrinho aberto ao mesmo tempo têm cada um o seu monitor."""
    return [a for a in aberturas() if aberta_em(a, dia)]


def abertura_de(codigo: str | None) -> dict | None:
    codigo = str(codigo or "").upper()
    return next((a for a in aberturas() if a["codigo"] == codigo), None)


# ── Leitura: Active Campaign ───────────────────────────────────────────────────

class _Active:
    def __init__(self):
        self.raiz = os.environ["AC_API_URL"].rstrip("/")
        self.base = self.raiz + "/api/3"
        self.s = requests.Session()
        self.s.headers.update({"Api-Token": os.environ["AC_API_KEY"]})

    def _pedir(self, url: str, params: dict) -> dict:
        for tentativa in range(4):
            r = self.s.get(url, params=params, timeout=60)
            if r.status_code == 429:  # limite de 5 req/s da conta, dividido com o ETL e a integração
                time.sleep(2 + 2 * tentativa)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"Active Campaign: 429 persistente em {url}")

    def get(self, caminho: str, **params) -> dict:
        return self._pedir(f"{self.base}/{caminho}", params)

    def v1(self, acao: str, **params) -> list[dict]:
        """API v1 (admin/api.php): a única que lista quem abriu uma campanha de uma
        vez, 100 por página, da abertura mais recente pra mais antiga. Página
        vazia ou fora do fim volta []."""
        js = self._pedir(f"{self.raiz}/admin/api.php", {
            "api_action": acao, "api_key": os.environ["AC_API_KEY"], "api_output": "json", **params,
        })
        return [v for k, v in js.items() if k.isdigit() and isinstance(v, dict)]


_EMAIL_DO_CONTATO: dict[str, str] = {}   # id do contato no Active -> e-mail (não muda; vale o processo todo)

# Entradas já lidas, por automação. O carrinho dura ~2 semanas e a automação é a
# mesma dos três cursos: reler tudo a cada 5 min seriam dezenas de páginas por
# rodada, dividindo o limite de 5 req/s com o ETL. Depois da primeira leitura, só
# relê as entradas dos últimos _RELEITURA_MIN antes da leitura anterior: é o
# bastante pra pegar as novas e o status de quem saiu da fila (a espera é de 10 min).
_ENTRADAS: dict[str, dict] = {}
_RELEITURA_MIN = 40


def _entradas_automacao(ac: _Active, automacao_id: str, desde: datetime) -> list[dict]:
    """Entradas na automação desde `desde`, da mais nova pra mais velha."""
    cache = _ENTRADAS.get(automacao_id)
    if cache is None or desde < cache["desde"]:
        cache = {"linhas": {}, "desde": desde, "lido_em": None}
        corte = desde
    else:
        corte = max(desde, cache["lido_em"] - timedelta(minutes=_RELEITURA_MIN))
    comeco = datetime.now(BR)
    off = 0
    while True:
        pg = ac.get(f"automations/{automacao_id}/contactAutomations",
                    limit=100, offset=off, **{"orders[adddate]": "DESC"}).get("contactAutomations", [])
        for x in pg:
            cache["linhas"][x["id"]] = x
        mais_velha = min((datetime.fromisoformat(x["adddate"]) for x in pg), default=corte)
        if len(pg) < 100 or mais_velha < corte or off > 20000:
            break
        off += 100
    cache["lido_em"] = comeco
    _ENTRADAS[automacao_id] = cache
    linhas = [x for x in cache["linhas"].values() if datetime.fromisoformat(x["adddate"]) >= desde]
    faltam = sorted({x["contact"] for x in linhas} - set(_EMAIL_DO_CONTATO))
    for i in range(0, len(faltam), 100):
        for c in ac.get("contacts", ids=",".join(faltam[i:i + 100]), limit=100).get("contacts", []):
            _EMAIL_DO_CONTATO[c["id"]] = (c.get("email") or "").strip().lower()
    for x in linhas:
        x["_quando"] = datetime.fromisoformat(x["adddate"]).astimezone(BR)
        x["_email"] = _EMAIL_DO_CONTATO.get(x["contact"])
    return linhas


def juntar_pagina_aberturas(itens: list[dict], desde: datetime, acumulado: dict[str, datetime]) -> bool:
    """Junta uma página da campaign_report_open_list em `acumulado` {e-mail: abertura
    mais recente}. A lista vem da mais recente pra mais antiga, então devolve True
    (pode parar) quando a página acaba ou já chegou em antes de `desde`."""
    if not itens:
        return True
    for x in itens:
        email = (x.get("email") or "").strip().lower()
        try:
            quando = datetime.fromisoformat(x["tstamp_iso"]).astimezone(BR)
        except (KeyError, ValueError):
            continue
        if not email or quando < desde:
            continue
        if email not in acumulado or quando > acumulado[email]:
            acumulado[email] = quando
    try:
        return datetime.fromisoformat(itens[-1]["tstamp_iso"]) < desde
    except (KeyError, ValueError):
        return True


_CAMPANHAS: dict = {"em": 0.0, "ids": []}
_MAX_PAGINAS_ABERTURA = 60   # 6.000 pessoas por e-mail: sobra pro dia mais cheio já visto (~950 no PES-NOV-26)


def _campanhas_da_automacao(ac: _Active, automacao_id: str) -> list[str]:
    """Os e-mails de boas-vindas (um por curso, mais cópias) são campanhas da
    automação. Descobre sozinho, pra cópia nova entrar sem mexer em config."""
    if time.monotonic() - _CAMPANHAS["em"] < 3600 and _CAMPANHAS["ids"]:
        return _CAMPANHAS["ids"]
    camps = ac.get(f"automations/{automacao_id}/campaigns").get("campaigns", [])
    ids = [str(c["id"]) for c in camps if str(c.get("status")) == "1" and int(c.get("send_amt") or 0) > 0]
    _CAMPANHAS.update(em=time.monotonic(), ids=ids)
    return ids


def _aberturas(ac: _Active, automacao_id: str, desde: datetime) -> dict[str, datetime]:
    """E-mail -> abertura mais recente de algum e-mail de boas-vindas, desde `desde`."""
    acumulado: dict[str, datetime] = {}
    for cid in _campanhas_da_automacao(ac, automacao_id):
        for pagina in range(1, _MAX_PAGINAS_ABERTURA + 1):
            if juntar_pagina_aberturas(ac.v1("campaign_report_open_list", campaignid=cid, page=pagina),
                                       desde, acumulado):
                break
    return acumulado


# ── Leitura: vendas (banco operacional) ────────────────────────────────────────

def _compras(ab: dict, inicio: datetime, fim: datetime) -> tuple[dict[str, tuple[datetime, str]], dict[str, datetime]]:
    """(e-mail -> (hora que conta, produto) da primeira compra na janela, e-mail ->
    hora do pedido quando ela é diferente da aprovação). Hotmart + TMB."""
    from frontend.db import _get_users_engine  # noqa: PLC0415
    from frontend.db_readers._vendas_comum import _hm_data_sql  # noqa: PLC0415

    # Pedido ou aprovação na janela: o filtro do banco vai de um dia antes (fuso) até
    # alguns dias depois do fim (parcelamento aprovado depois do fechamento).
    pedido_sql, aprov_sql = _hm_data_sql("data_da_transacao"), _hm_data_sql("confirmacao_do_pagamento")
    with _get_users_engine().connect() as conn:
        hm = conn.execute(text(f"""
            SELECT lower(trim(email_do_a_comprador_a)) AS email, produto,
                   data_da_transacao, confirmacao_do_pagamento
            FROM hotmart_clean_oficial
            WHERE codigo_do_produto::text = ANY(:ids)
              AND (COALESCE({pedido_sql}, {aprov_sql}) BETWEEN :d0 AND :d1
                   OR {aprov_sql} BETWEEN :d0 AND :d1)
        """), {"ids": ab["produtos"], "d0": inicio.date() - timedelta(days=1),
               "d1": fim.date()}).mappings().all()
        tmb = conn.execute(text("""
            SELECT lower(trim(email_cliente)) AS email, produto, data_efetivado
            FROM tmb_clean_oficial
            WHERE produto ILIKE :p AND data_efetivado >= :d0 AND data_efetivado < :d1
        """), {"p": ab["tmb_produto_like"], "d0": inicio.replace(tzinfo=None),
               "d1": fim.replace(tzinfo=None)}).mappings().all()

    compras: dict[str, tuple[datetime, str]] = {}
    pedidos: dict[str, datetime] = {}

    def _guardar(email, quando, produto, pedido=None):
        if not email or any(t in email for t in _EMAILS_TESTE) or not quando:
            return
        if email not in compras or quando < compras[email][0]:
            compras[email] = (quando, produto)
            if pedido and abs(quando - pedido) > timedelta(minutes=30):
                pedidos[email] = pedido
            else:
                pedidos.pop(email, None)

    for r in hm:
        pedido, aprovacao = parse_hm(r["data_da_transacao"]), parse_hm(r["confirmacao_do_pagamento"])
        _guardar(r["email"], hora_da_compra(pedido, aprovacao, inicio, fim), (r["produto"] or "").strip(), pedido)
    for r in tmb:
        q = r["data_efetivado"]
        if q is not None:
            q = q.replace(tzinfo=BR) if q.tzinfo is None else q.astimezone(BR)
        _guardar(r["email"], q if q and inicio <= q < fim else None, f"{(r['produto'] or '').strip()} · TMB")
    return compras, pedidos


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
    """Retrato do carrinho de `ab`, da abertura até `agora` (ou até o fechamento, se já passou)."""
    cfg = config()
    bucket = int(cfg.get("intervalo_min") or 5)
    tolerancia = int(cfg.get("tolerancia_min") or 15)
    inicio = datetime.combine(ab["dia"], dtime(0), BR)
    fim = datetime.combine(ab["fim"] + timedelta(days=1), dtime(0), BR)
    agora_real = agora or datetime.now(BR)
    agora = agora_real
    ao_vivo = inicio <= agora_real < fim
    # A curva de 5 em 5 min é de um dia só: hoje, com o carrinho aberto; depois, o da abertura.
    dia_curva = agora_real.date() if ao_vivo else ab["dia"]
    ini_curva = datetime.combine(dia_curva, dtime(0), BR)
    fim_curva = min(agora_real, ini_curva + timedelta(days=1) - timedelta(seconds=1))

    ac = _Active()
    linhas = _entradas_automacao(ac, str(cfg["automacao_id"]), inicio - timedelta(days=1))
    compras, pedidos = _compras(ab, inicio, fim)
    compras = {e: v for e, v in compras.items() if v[0] <= agora}
    # Abertura do e-mail de boas-vindas: medida pelo pixel, então Apple Mail pode
    # marcar sozinho e quem bloqueia imagem aparece como não aberto. Se a leitura
    # falhar, a página segue sem a coluna (abertos = None), não cai.
    try:
        abertos: dict[str, datetime] | None = _aberturas(ac, str(cfg["automacao_id"]), inicio)
    except Exception:  # noqa: BLE001
        logger.warning("Monitor de boas-vindas: aberturas do e-mail indisponíveis para %s", ab["codigo"], exc_info=True)
        abertos = None

    # Entradas e fila contam só os compradores deste lançamento: a automação é a
    # mesma dos três cursos, e quem comprou outro curso no período não entra na conta.
    # Vale qualquer entrada desde a véspera da abertura, mesmo antes da compra que
    # ficou no banco: em 13/11 duas compradoras tinham entrado (e aberto o e-mail)
    # em 12/11, numa compra anterior que não ficou na tabela.
    na_automacao: set[str] = set()
    entrou: dict[str, datetime] = {}
    na_fila: set[str] = set()
    outras: set[str] = set()
    for x in linhas:
        e = x["_email"]
        if not e:
            continue
        if e in compras:
            na_automacao.add(e)
            if x["_quando"] >= inicio:
                entrou[e] = min(entrou.get(e, x["_quando"]), x["_quando"])
            if str(x.get("status")) == "1":
                na_fila.add(e)
        elif inicio <= x["_quando"] <= agora:
            outras.add(e)

    fora = [e for e in compras if e not in na_automacao]
    grupos = classificar(compras, na_automacao, _comprou_antes(fora, inicio), agora, tolerancia)

    hist = _FILA.setdefault((ab["codigo"], dia_curva.isoformat()), {})
    if ao_vivo:
        hist[chave_bucket(agora, bucket)] = len(na_fila)

    por_produto: dict[str, dict] = {}
    for e, (_, produto) in compras.items():
        r = por_produto.setdefault(produto, {"produto": produto, "compradores": 0, "na_automacao": 0})
        r["compradores"] += 1
        r["na_automacao"] += e in na_automacao

    # Uma linha por comprador, pra quem acompanha os alunos (página e CSV). Mais novo
    # primeiro; "entrou_hora" vazio + situação "entrou" = já estava na automação
    # antes da abertura. "pedido_txt" = pediu bem antes de aprovar (parcelamento/boleto).
    def _txt(quando: datetime | None) -> str | None:
        return quando.strftime("%d/%m %H:%M") if quando else None

    pessoas = sorted((
        {"email": e, "quando": q, "hora": q.strftime("%H:%M"), "quando_txt": _txt(q), "produto": p,
         "pedido_txt": _txt(pedidos.get(e)),
         "situacao": grupos["situacao"][e],
         "entrou_hora": _txt(entrou.get(e)),
         "na_fila": e in na_fila,
         "abriu": (abertos or {}).get(e),
         "abriu_txt": _txt((abertos or {}).get(e))}
        for e, (q, p) in compras.items()
    ), key=lambda r: r["quando"], reverse=True)
    contagem = {k: sum(1 for r in pessoas if r["situacao"] == k) for k in SITUACOES}
    abriram = sum(1 for r in pessoas if r["situacao"] == "entrou" and r["abriu"])
    contagem["nao_abriu"] = contagem["entrou"] - abriram if abertos is not None else 0

    # Um resumo por dia do carrinho (pela hora que conta da compra).
    por_dia = []
    ultimo = max([min(ab["fim"], agora.date()), *(r["quando"].date() for r in pessoas)])
    d = ab["dia"]
    while d <= ultimo:
        doz = [r for r in pessoas if r["quando"].date() == d]
        por_dia.append({
            "dia": d, "compradores": len(doz),
            **{k: sum(1 for r in doz if r["situacao"] == k) for k in SITUACOES},
            "abriram": sum(1 for r in doz if r["situacao"] == "entrou" and r["abriu"]),
            "depois_do_fim": d > ab["fim"],
        })
        d += timedelta(days=1)

    tempos_curva = [q for q, _ in compras.values() if q.date() == dia_curva]
    entradas_curva = [t for t in entrou.values() if t.date() == dia_curva]

    return {
        "codigo": ab["codigo"], "curso": ab.get("curso"), "dia": ab["dia"], "fim": ab["fim"],
        "dia_curva": dia_curva, "por_dia": por_dia,
        "pedido_antes": sum(1 for r in pessoas if r["pedido_txt"]),
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
        "pessoas": pessoas,
        "contagem": contagem,
        "aberturas_ok": abertos is not None,
        "abriram": abriram,
        "serie": montar_serie(ini_curva, fim_curva, tempos_curva, entradas_curva, hist, bucket),
    }


# ── Cache + laço de fundo ──────────────────────────────────────────────────────

_ULTIMO: dict[str, tuple[float, dict]] = {}
_TRAVA = threading.Lock()
ESTADO: dict = {"ultima_rodada": None, "erro": None}


def obter(ab: dict, max_idade_s: int = 270) -> dict:
    """Retrato em cache (até `max_idade_s`) ou recém-calculado. Uma conta por vez:
    duas abas abertas não dobram as chamadas ao Active."""
    chave = f"{ab['codigo']}|{ab['dia']}"
    if datetime.now(BR).date() > ab["fim"] + timedelta(days=2):
        max_idade_s = max(max_idade_s, 3600)   # carrinho fechado: o retrato quase não muda
    with _TRAVA:
        em, snap = _ULTIMO.get(chave, (0.0, None))
        if snap is not None and time.monotonic() - em < max_idade_s:
            return snap
        snap = calcular(ab)
        _ULTIMO[chave] = (time.monotonic(), snap)
        return snap


def rodada(hoje: date | None = None) -> list[dict]:
    """Uma leitura do laço. Só calcula os lançamentos com carrinho aberto hoje
    (da abertura ao fim), cada um separado; um que falhe não impede os outros."""
    hoje = hoje or datetime.now(BR).date()
    snaps, erros = [], []
    for ab in abertas_em(hoje):
        try:
            snaps.append(obter(ab, max_idade_s=60))
        except Exception as e:  # noqa: BLE001
            erros.append(f"{ab['codigo']}: {str(e)[:200]}")
            logger.exception("Monitor de boas-vindas: leitura de %s falhou", ab["codigo"])
    ESTADO.update(ultima_rodada=datetime.now(BR), erro="; ".join(erros) or None)
    return snaps


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
    logger.info("Monitor de boas-vindas agendado: calcula da abertura ao fim de cada carrinho")
