"""
frontend/db_readers/publicos.py — leitura da página /publicos (públicos em uso por lançamento).

Lê `publicos_snapshot` / `publicos_uso` / `publicos_tamanho_diario` (gravadas por `etl/etl_publicos.py`) e cruza com
o gasto e os leads dos conjuntos/grupos (`meta_ads_daily`, `google_ads_daily`). Não chama Meta nem Google.

Os alertas são calculados AQUI, a partir do banco, para uma mudança de regra valer sem recoletar:
- as violações da SEG-4 vêm de `scripts.ads.publicos.problemas_publico` (a mesma conferência do terminal);
- tamanho, lista vazia/velha e nome repetido saem dos dados do snapshot.

Limite do Meta: a API não informa tamanho abaixo de 1.000 (o menor valor é 1000). Por isso o alerta "< 500 pessoas"
só é confiável no Google; no Meta o sinal de lista pequena é o `delivery_status`/`operation_status` e a faixa "≤ 1.000".

Gasto NÃO é aditivo por público: um conjunto com 13 públicos tem um gasto só. A coluna do público é "gasto dos
conjuntos que o incluem" e a tela não a soma; a visão por conjunto mostra o gasto uma vez.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from frontend.db import _get_engine
from logger import get_logger
from scripts.ads import padroes as P
from scripts.ads.publicos import lancamento_do_nome, problemas_publico, produto_do_nome, sujeito_a_regra

logger = get_logger("db")

# Lista de cliente sem atualização há mais que isto precisa ser repovoada (só o Meta informa a data).
DIAS_LISTA_VELHA = 30
_TZ_BR = timezone(timedelta(hours=-3))
_TIPOS_FORA_DA_CONFERENCIA = {"INTERESSE", "SEGMENTO"}   # a SEG-4 só confere listas (igual a scripts/ads/publicos.py)


# ---------------------------------------------------------------------------- dataclasses
@dataclass
class Alerta:
    nivel: str      # 'critico' | 'atencao' | 'info'
    codigo: str     # 'pequeno' | 'vazia' | 'nao_entrega' | 'lista_velha' | 'outro_lancamento' | 'nome_repetido' | ...
    texto: str


@dataclass
class Desempenho:
    gasto_3d: float = 0.0
    leads_3d: float = 0.0
    gasto: float = 0.0
    leads: float = 0.0

    @property
    def cpl_3d(self) -> float | None:
        return self.gasto_3d / self.leads_3d if self.leads_3d else None

    @property
    def cpl(self) -> float | None:
        return self.gasto / self.leads if self.leads else None


@dataclass
class PublicoRef:
    """Um público dentro de um conjunto/grupo (visão por conjunto)."""
    id: str
    nome: str
    tipo: str
    tamanho: int | None
    tamanho_label: str


@dataclass
class GrupoUso:
    plataforma: str
    campanha_id: str
    campanha_nome: str
    campanha_status: str
    grupo_id: str
    grupo_nome: str
    grupo_status: str
    temperatura: str            # quente | frio | especifico | outra
    etapa: str                  # captacao | pre_quali | outra
    inclui: list[PublicoRef] = field(default_factory=list)
    exclui: list[PublicoRef] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)      # SEG-4
    desempenho: Desempenho = field(default_factory=Desempenho)

    @property
    def rodando(self) -> bool:
        return self.campanha_status in ("ACTIVE", "ENABLED") and self.grupo_status in ("ACTIVE", "ENABLED", "")


@dataclass
class PublicoLinha:
    plataforma: str
    id: str
    nome: str
    conta: str
    tipo: str                   # rótulo curto: LISTA / SITE / ENGAJAMENTO / SEMELHANTE / INTERESSE / SEGMENTO ...
    tipo_origem: str            # subtype (Meta) / type (Google)
    tamanho: int | None
    tamanho_label: str
    status: str
    status_detalhe: str
    retencao_dias: int | None
    atualizado_em: datetime | None
    delta_7d: int | None
    n_inclui: int = 0
    n_exclui: int = 0
    temperaturas: list[str] = field(default_factory=list)
    etapas: list[str] = field(default_factory=list)
    desempenho: Desempenho = field(default_factory=Desempenho)
    alertas: list[Alerta] = field(default_factory=list)

    @property
    def severidade(self) -> str:
        for n in ("critico", "atencao"):
            if any(a.nivel == n for a in self.alertas):
                return n
        return "ok"


@dataclass
class PublicosView:
    lancamento: str
    coletado_em: datetime | None
    publicos: list[PublicoLinha]
    grupos: list[GrupoUso]
    atencao: list[dict]         # [{nivel, onde, texto}] — o bloco "Precisa de atenção" do topo

    @property
    def vazio(self) -> bool:
        return not self.grupos

    @property
    def coletado_br(self) -> str:
        return self.coletado_em.astimezone(_TZ_BR).strftime("%d/%m %H:%M") if self.coletado_em else "—"


# ---------------------------------------------------------------------------- funções puras (testadas)
def temperatura_da_campanha(nome: str) -> str:
    n = nome.lower()
    for chave, rotulo in (("[quente]", "quente"), ("[frio]", "frio"), ("[específico]", "especifico"),
                          ("[especifico]", "especifico")):
        if chave in n:
            return rotulo
    return "outra"


def etapa_da_campanha(nome: str) -> str:
    n = nome.lower()
    if "pré-qualifica" in n or "pre-qualifica" in n:
        return "pre_quali"
    if "capta" in n:
        return "captacao"
    return "outra"


def rotulo_tamanho(plataforma: str, efetivo: int | None, inferior: int | None, superior: int | None) -> str:
    if efetivo is None:
        return "—"
    if plataforma == "meta":
        # o piso da API é 1.000: "1.000" quer dizer "até 1.000", não "exatamente 1.000"
        if inferior is not None and inferior <= 1000:
            return "≤ 1.000"
        if inferior is not None and superior and superior != inferior:
            return f"{inferior:,}–{superior:,}".replace(",", ".")
    return f"{efetivo:,}".replace(",", ".")


def alertas_do_publico(p: dict, *, incluido_em: list[dict], hoje: date, lancamento: str) -> list[Alerta]:
    """`p`: linha do snapshot (+ nome/tipo_uso). `incluido_em`: grupos que INCLUEM o público, cada um com
    `inclui_ids` (todos os públicos incluídos no grupo) e `tamanhos` ({id: tamanho})."""
    out: list[Alerta] = []
    plataforma, tam, nome = p["plataforma"], p.get("tamanho_efetivo"), p.get("nome") or p["publico_id"]
    incluido = bool(incluido_em)
    minimo = P.PUBLICO_MINIMO

    if incluido and plataforma == "google" and tam is not None and tam < minimo:
        so_ele = [g for g in incluido_em
                  if all((g["tamanhos"].get(i) is not None and g["tamanhos"][i] < minimo) for i in g["inclui_ids"])]
        if tam == 0:
            out.append(Alerta("critico" if so_ele else "atencao", "vazia",
                              "lista vazia (0 pessoas)" + (" — é o único público de " + str(len(so_ele)) +
                                                          " grupo(s): não entregam" if so_ele else "")))
        else:
            out.append(Alerta("critico" if so_ele else "atencao", "pequeno",
                              f"{tam} pessoas (< {minimo}: não entrega)" + (f" — único público de {len(so_ele)} grupo(s)"
                                                                           if so_ele else "")))
    if incluido and plataforma == "meta":
        if p.get("status") not in (None, "") and str(p.get("status")) != "200":
            out.append(Alerta("atencao", "entrega", f"status de entrega {p.get('status')}"
                              + (f" ({p['status_detalhe']})" if p.get("status_detalhe") else "")))
        if tam is None and p.get("tipo_uso") not in _TIPOS_FORA_DA_CONFERENCIA:   # interesse nunca tem tamanho
            out.append(Alerta("atencao", "sem_tamanho", "tamanho desconhecido"))
    if incluido and p.get("elegivel") is False:
        out.append(Alerta("critico", "inelegivel", "não elegível para exibição"))
    if incluido and (p.get("status") or "").upper() == "CLOSED":
        out.append(Alerta("critico", "fechada", "lista fechada (membership CLOSED)"))

    if p.get("tipo_uso") == "LISTA" and p.get("atualizado_em") and incluido:
        dias = (hoje - p["atualizado_em"].astimezone(_TZ_BR).date()).days
        if dias > DIAS_LISTA_VELHA:
            out.append(Alerta("atencao", "lista_velha", f"lista sem atualização há {dias} dias (repovoar)"))

    outro = lancamento_do_nome(nome)
    if outro and outro != lancamento.upper() and incluido:
        pequeno = tam is not None and tam < minimo and plataforma == "google"
        out.append(Alerta("atencao" if pequeno else "info", "outro_lancamento",
                          f"público de outro lançamento ({outro})" + (" que já esvaziou" if pequeno else "")))
    return out


def violacoes_seg4(g: GrupoUso, conta: str, lancamento: str, tamanhos: dict[str, int | None]) -> list[str]:
    """Mesma conferência do terminal (`scripts.ads.publicos`), a partir dos dados do banco."""
    if not sujeito_a_regra(g.campanha_nome):
        return []
    produto = produto_do_nome(g.campanha_nome)
    aluno = (P.ALUNOS_POR_PRODUTO.get(produto or "") or {}).get("meta" if g.plataforma == "meta" else "google")
    if isinstance(aluno, dict):
        aluno = aluno.get(conta)
    listas = lambda refs: {r.id: r.nome for r in refs if r.tipo not in _TIPOS_FORA_DA_CONFERENCIA}
    probs = problemas_publico(
        g.grupo_nome, frio=g.temperatura == "frio", incluidos=listas(g.inclui), excluidos=listas(g.exclui),
        aluno_id=aluno, lancamento=lancamento_do_nome(g.campanha_nome), produto=produto, tamanhos=tamanhos)
    if g.plataforma == "google" and not g.inclui and g.temperatura != "frio":
        probs.append(f"{g.grupo_nome}: sem público (nem agrupado nem lista) — confirmar que não roda aberto")
    return probs


def montar_visao(lancamento: str, usos: list[dict], snaps: dict[tuple[str, str, str], dict],
                 desempenho: dict[tuple[str, str], Desempenho], tamanho_7d: dict[tuple[str, str, str], int | None],
                 hoje: date | None = None) -> PublicosView:
    """Junta o que veio do banco. `snaps`: {(plataforma, conta, publico_id): linha}. `desempenho`: {(plataforma,
    grupo_id): Desempenho}. Pura: nenhum acesso a banco."""
    hoje = hoje or datetime.now(_TZ_BR).date()

    def snap_de(u: dict) -> dict:
        # Meta: conta '' (id único); Google: conta da campanha
        return snaps.get((u["plataforma"], "" if u["plataforma"] == "meta" else u["conta"], u["publico_id"])) or {}

    # --- grupos
    grupos: dict[tuple[str, str], GrupoUso] = {}
    conta_do_grupo: dict[tuple[str, str], str] = {}
    for u in usos:
        k = (u["plataforma"], u["grupo_id"])
        g = grupos.get(k)
        if g is None:
            g = grupos[k] = GrupoUso(
                plataforma=u["plataforma"], campanha_id=u["campanha_id"], campanha_nome=u["campanha_nome"] or "",
                campanha_status=u["campanha_status"] or "", grupo_id=u["grupo_id"], grupo_nome=u["grupo_nome"] or "",
                grupo_status=u["grupo_status"] or "", temperatura=temperatura_da_campanha(u["campanha_nome"] or ""),
                etapa=etapa_da_campanha(u["campanha_nome"] or ""), desempenho=desempenho.get(k, Desempenho()))
            conta_do_grupo[k] = u["conta"]
        if u["papel"] == "nenhum":
            continue
        s = snap_de(u)
        tam = s.get("tamanho_efetivo")
        ref = PublicoRef(u["publico_id"], u["publico_nome"] or u["publico_id"], u["publico_tipo"] or "OUTRO", tam,
                         rotulo_tamanho(u["plataforma"], tam, s.get("tamanho_inferior"), s.get("tamanho_superior")))
        (g.inclui if u["papel"] == "inclui" else g.exclui).append(ref)

    for g in grupos.values():
        g.inclui.sort(key=lambda r: r.nome.lower())
        g.exclui.sort(key=lambda r: r.nome.lower())

    # --- públicos
    chaves: dict[tuple[str, str, str], dict] = {}
    for u in usos:
        if u["papel"] == "nenhum":
            continue
        k = (u["plataforma"], "" if u["plataforma"] == "meta" else u["conta"], u["publico_id"])
        d = chaves.setdefault(k, {"nome": u["publico_nome"], "tipo_uso": u["publico_tipo"], "inclui": [], "exclui": []})
        d["inclui" if u["papel"] == "inclui" else "exclui"].append(grupos[(u["plataforma"], u["grupo_id"])])

    nomes: dict[tuple[str, str], set[str]] = {}
    for (plat, _c, pid), d in chaves.items():
        nomes.setdefault((plat, (d["nome"] or "").strip().lower()), set()).add(pid)

    publicos: list[PublicoLinha] = []
    for k, d in chaves.items():
        plat, conta, pid = k
        s = snaps.get(k) or {}
        nome = s.get("nome") or d["nome"] or pid
        tam = s.get("tamanho_efetivo")
        incl = [{"inclui_ids": [r.id for r in g.inclui],
                 "tamanhos": {r.id: r.tamanho for r in g.inclui}} for g in d["inclui"]]
        dados = {**s, "plataforma": plat, "publico_id": pid, "nome": nome, "tipo_uso": d["tipo_uso"]}
        linha = PublicoLinha(
            plataforma=plat, id=pid, nome=nome, conta=s.get("conta_dona") or conta, tipo=d["tipo_uso"] or "OUTRO",
            tipo_origem=s.get("tipo") or "", tamanho=tam,
            tamanho_label=rotulo_tamanho(plat, tam, s.get("tamanho_inferior"), s.get("tamanho_superior")),
            status=str(s.get("status") or ""), status_detalhe=s.get("status_detalhe") or "",
            retencao_dias=s.get("retencao_dias"), atualizado_em=s.get("atualizado_em"),
            delta_7d=(tam - tamanho_7d[k]) if tam is not None and tamanho_7d.get(k) is not None else None,
            n_inclui=len(d["inclui"]), n_exclui=len(d["exclui"]),
            temperaturas=sorted({g.temperatura for g in d["inclui"]}), etapas=sorted({g.etapa for g in d["inclui"]}))
        linha.alertas = alertas_do_publico(dados, incluido_em=incl, hoje=hoje, lancamento=lancamento)
        outros = sorted(x for x in nomes[(plat, (d["nome"] or "").strip().lower())] if x != pid)
        if outros:
            linha.alertas.append(Alerta("atencao", "nome_repetido", "mesmo nome de outro público (ID " + ", ".join(outros) + ")"))
        # gasto dos conjuntos que INCLUEM o público: cada conjunto conta uma vez
        for g in d["inclui"]:
            linha.desempenho.gasto_3d += g.desempenho.gasto_3d
            linha.desempenho.leads_3d += g.desempenho.leads_3d
            linha.desempenho.gasto += g.desempenho.gasto
            linha.desempenho.leads += g.desempenho.leads
        publicos.append(linha)

    # --- SEG-4 por grupo + bloco de atenção
    for k, g in grupos.items():
        tams = {r.id: r.tamanho for r in g.inclui}
        g.problemas = violacoes_seg4(g, conta_do_grupo[k], lancamento, tams)

    atencao: list[dict] = []
    for p in publicos:
        for a in p.alertas:
            if a.nivel in ("critico", "atencao"):
                atencao.append({"nivel": a.nivel, "onde": f"{p.nome} ({p.id})", "texto": a.texto})
    for g in grupos.values():
        for txt in g.problemas:
            atencao.append({"nivel": "critico" if "NÃO ENTREGA" in txt else "atencao",
                            "onde": f"{g.campanha_nome} → {g.grupo_nome}", "texto": txt.split(": ", 1)[-1]})
    atencao.sort(key=lambda a: (a["nivel"] != "critico", a["onde"]))
    ordem = {"critico": 0, "atencao": 1, "ok": 2}
    publicos.sort(key=lambda p: (ordem[p.severidade], -p.desempenho.gasto, p.nome.lower()))
    lista_grupos = sorted(grupos.values(), key=lambda g: (g.plataforma, g.campanha_nome, g.grupo_nome))
    coletas = [s["coletado_em"] for s in snaps.values() if s.get("coletado_em")]
    return PublicosView(lancamento=lancamento, coletado_em=max(coletas) if coletas else None, publicos=publicos,
                        grupos=lista_grupos, atencao=atencao)


# ---------------------------------------------------------------------------- banco
def _desempenho(conn, lancamento: str, hoje: date) -> dict[tuple[str, str], Desempenho]:
    corte = hoje - timedelta(days=2)
    out: dict[tuple[str, str], Desempenho] = {}
    for plat, sql in (
        ("meta", """SELECT adset_id AS gid, SUM(spend) AS gasto, SUM(leads) AS leads,
                           SUM(spend) FILTER (WHERE date >= :corte) AS gasto_3d,
                           SUM(leads) FILTER (WHERE date >= :corte) AS leads_3d
                    FROM meta_ads_daily WHERE lancamento_codigo = :l GROUP BY adset_id"""),
        ("google", """SELECT ad_group_id AS gid, SUM(cost) AS gasto, SUM(conversions) AS leads,
                             SUM(cost) FILTER (WHERE date >= :corte) AS gasto_3d,
                             SUM(conversions) FILTER (WHERE date >= :corte) AS leads_3d
                      FROM google_ads_daily WHERE lancamento_codigo = :l GROUP BY ad_group_id"""),
    ):
        for r in conn.execute(text(sql), {"l": lancamento, "corte": corte}).mappings():
            f = lambda v: float(v or 0)
            out[(plat, str(r["gid"]))] = Desempenho(f(r["gasto_3d"]), f(r["leads_3d"]), f(r["gasto"]), f(r["leads"]))
    return out


def read_publicos(launch_code: str) -> PublicosView | None:
    """None = sem coleta ainda (ETL não rodou para o lançamento) ou falha de leitura (a página mostra o aviso)."""
    if not launch_code:
        return None
    hoje = datetime.now(_TZ_BR).date()
    try:
        with _get_engine().connect() as conn:
            usos = [dict(r) for r in conn.execute(text("""SELECT plataforma, conta, campanha_id, campanha_nome,
                campanha_status, grupo_id, grupo_nome, grupo_status, publico_id, publico_nome, publico_tipo, papel
                FROM publicos_uso WHERE lancamento_codigo = :l"""), {"l": launch_code}).mappings()]
            if not usos:
                return None
            snaps = {(r["plataforma"], r["conta"], r["publico_id"]): dict(r) for r in conn.execute(text("""
                SELECT s.* FROM publicos_snapshot s WHERE EXISTS (SELECT 1 FROM publicos_uso u
                WHERE u.lancamento_codigo = :l AND u.plataforma = s.plataforma AND u.publico_id = s.publico_id)"""),
                {"l": launch_code}).mappings()}
            tam7 = {(r["plataforma"], r["conta"], r["publico_id"]): r["tamanho"] for r in conn.execute(text("""
                SELECT DISTINCT ON (plataforma, conta, publico_id) plataforma, conta, publico_id, tamanho
                FROM publicos_tamanho_diario WHERE data <= :d AND data >= :d - 14
                ORDER BY plataforma, conta, publico_id, data DESC"""), {"d": hoje - timedelta(days=7)}).mappings()}
            desemp = _desempenho(conn, launch_code, hoje)
    except Exception:
        # Tabelas ainda inexistentes (ETL nunca rodou) ou banco fora: a página mostra "sem coleta", não quebra.
        logger.exception("read_publicos: falha para %s", launch_code)
        return None
    return montar_visao(launch_code, usos, snaps, desemp, tam7, hoje)
