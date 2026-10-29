"""
Encurtador de links (página /links): leitura e gravação no schema `encurtador`
do banco comercial (SUPABASE_USERS_URL).

As tabelas são criadas pelo app Brabo Links na subida (app/db.py de lá), que
também grava os cliques. Aqui só se lê clique; link se cria e edita. O guard de
somente-leitura da engine comercial só barra hotmart/tmb.

Cliques de robô (pré-visualização do WhatsApp, Instagram etc.) ficam gravados
com bot=true e saem de todas as contas.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from frontend.db import _get_users_engine
from frontend.services.links import UTMS, LinkInvalido

TZ = ZoneInfo("America/Sao_Paulo")
_COLS = ("id, slug, destino, titulo, categoria, campanha, utm_source, utm_medium, utm_campaign, "
         "utm_content, utm_term, ativo, criado_por, criado_em, atualizado_em")


def hoje() -> date:
    return datetime.now(TZ).date()


def _d(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def link(link_id: int) -> dict | None:
    with _get_users_engine().connect() as conn:
        r = conn.execute(text(f"SELECT {_COLS} FROM encurtador.links WHERE id = :id"), {"id": link_id}).mappings().first()
    return dict(r) if r else None


def slug_existe(slug: str, exceto: int | None = None) -> bool:
    with _get_users_engine().connect() as conn:
        return conn.execute(
            text("SELECT 1 FROM encurtador.links WHERE slug = :s AND id <> :x"),
            {"s": slug, "x": exceto or 0},
        ).first() is not None


def criar(campos: dict, autor: str) -> dict:
    agora = datetime.now(timezone.utc)
    try:
        with _get_users_engine().begin() as conn:
            r = conn.execute(text(f"""
                INSERT INTO encurtador.links (slug, destino, titulo, categoria, campanha, {", ".join(UTMS)},
                                              ativo, criado_por, criado_em, atualizado_em)
                VALUES (:slug, :destino, :titulo, :categoria, :campanha, {", ".join(":" + k for k in UTMS)},
                        true, :autor, :agora, :agora)
                RETURNING {_COLS}
            """), {**campos, "autor": autor[:200], "agora": agora}).mappings().one()
    except IntegrityError:
        raise LinkInvalido("Esse nome acabou de ser usado por outra pessoa. Escolha outro.", 409) from None
    return dict(r)


def atualizar(link_id: int, campos: dict) -> dict | None:
    """Atualiza e devolve o link (None se não existe). `atualizado_em` é o que o
    Brabo Links usa pra puxar a mudança pro cache de redirecionamento."""
    sets = ", ".join(f"{k} = :{k}" for k in campos)
    try:
        with _get_users_engine().begin() as conn:
            r = conn.execute(
                text(f"UPDATE encurtador.links SET {sets}, atualizado_em = :agora WHERE id = :id RETURNING {_COLS}"),
                {**campos, "id": link_id, "agora": datetime.now(timezone.utc)},
            ).mappings().first()
    except IntegrityError:
        raise LinkInvalido("Esse nome já está em uso.", 409) from None
    return dict(r) if r else None


def listas(rows: list[dict] | None = None) -> tuple[list[str], dict[str, list[str]]]:
    """Campanhas e UTMs já usadas, pras sugestões dos campos. Com `rows` (o painel
    já leu os links) não vai ao banco."""
    if rows is None:
        with _get_users_engine().connect() as conn:
            rows = [dict(r) for r in conn.execute(
                text(f"SELECT campanha, {', '.join(UTMS)} FROM encurtador.links")).mappings()]
    camps = sorted({r["campanha"] for r in rows if r["campanha"]})
    usadas = {k: sorted({r[k] for r in rows if r[k]})[:200] for k in UTMS}
    return camps, usadas


def painel() -> dict:
    """Todos os links + cliques (sem robôs): total, 7 dias e série dos últimos 14 dias."""
    d0 = hoje()
    ini14 = d0 - timedelta(days=13)
    with _get_users_engine().connect() as conn:
        rows = [dict(r) for r in conn.execute(
            text(f"SELECT {_COLS} FROM encurtador.links ORDER BY criado_em DESC")).mappings()]
        # Uma ida só: total por link (dia NULL) + série por dia dos últimos 14.
        linhas = conn.execute(text("""
            SELECT link_id, NULL::date AS dia, count(*) FROM encurtador.cliques WHERE NOT bot GROUP BY link_id
            UNION ALL
            SELECT link_id, dia, count(*) FROM encurtador.cliques WHERE NOT bot AND dia >= :ini GROUP BY link_id, dia
        """), {"ini": ini14}).all()
    totais: dict[int, int] = {}
    por_link: dict[int, dict[date, int]] = defaultdict(dict)
    for lid, dia, n in linhas:
        if dia is None:
            totais[lid] = n
        else:
            por_link[lid][_d(dia)] = n
    dias = [ini14 + timedelta(days=i) for i in range(14)]
    geral: Counter = Counter()
    for r in rows:
        s = por_link.get(r["id"], {})
        r["serie14"] = [s.get(d, 0) for d in dias]
        r["cliques_7d"] = sum(r["serie14"][-7:])
        r["cliques_total"] = totais.get(r["id"], 0)
        for d, n in s.items():
            geral[d] += n
    return {
        "links": rows,
        "hoje": geral[d0],
        "ontem": geral[d0 - timedelta(days=1)],
        "sete": sum(geral[d] for d in dias[-7:]),
        "sete_antes": sum(geral[d] for d in dias[:7]),
    }


# Dimensões da página de um link: nome -> coluna (texto) de encurtador.cliques.
_DIMS = {
    "origem": "origem", "dispositivo": "dispositivo", "sistema": "sistema", "navegador": "navegador",
    "pais": "pais", "sites": "referer_host", **{k: k for k in UTMS}, "ref": "ref",
    "dia": "dia::text", "hora": "hora::text",
}


def estatisticas(link_id: int, dias: int | None) -> dict:
    """Tudo da página de um link. dias=None → desde a criação. Duas idas ao banco:
    os totais e um GROUP BY por dimensão, todos juntos num UNION ALL."""
    d0 = hoje()
    ini = d0 - timedelta(days=dias - 1) if dias else None
    cond = "link_id = :id" + (" AND dia >= :ini" if ini else "")
    params = {"id": link_id, **({"ini": ini} if ini else {})}
    union = " UNION ALL ".join(
        f"SELECT '{nome}' AS dim, {col} AS v, count(*) AS n FROM encurtador.cliques "
        f"WHERE {cond} AND NOT bot GROUP BY {col}"
        for nome, col in _DIMS.items()
    )
    with _get_users_engine().connect() as conn:
        tot = conn.execute(text(f"""
            SELECT count(*) FILTER (WHERE NOT bot),
                   count(DISTINCT visitante) FILTER (WHERE NOT bot),
                   count(*) FILTER (WHERE bot),
                   min(dia)
            FROM encurtador.cliques WHERE {cond}
        """), params).one()
        linhas = conn.execute(text(union), params).all()

    out: dict = {"total": tot[0] or 0, "unicos": tot[1] or 0, "bots": tot[2] or 0}
    grupos: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for dim, v, n in linhas:
        grupos[dim].append((v, n))
    por_dia = {_d(v): n for v, n in grupos["dia"]}
    por_hora = {int(v): n for v, n in grupos["hora"]}

    def top(nome, limite=8, vazio=False):
        itens = sorted(grupos[nome], key=lambda x: (-x[1], x[0] or ""))
        return [{"nome": v or "—", "n": n} for v, n in itens if vazio or v][:limite]

    for nome in ("origem", "dispositivo", "sistema", "navegador"):
        out[nome] = top(nome, vazio=True)
    for nome in ("pais", "sites", *UTMS):
        out[nome] = top(nome)
    out["ref"] = top("ref", 50)
    if ini is None:
        ini = _d(tot[3]) if tot[3] else d0
    n_dias = (d0 - ini).days + 1
    out["serie"] = [{"dia": (ini + timedelta(days=i)).isoformat(), "n": por_dia.get(ini + timedelta(days=i), 0)}
                    for i in range(n_dias)]
    out["horas"] = [por_hora.get(h, 0) for h in range(24)]
    out["media_dia"] = round(out["total"] / n_dias, 1) if n_dias else 0
    melhor = max(out["serie"], key=lambda x: x["n"]) if out["serie"] else None
    out["pico"] = melhor if melhor and melhor["n"] else None
    return out


_COLS_CSV = ("ts", "origem", "referer_host", "dispositivo", "sistema", "navegador", "pais", *UTMS,
             "ref", "visitante", "bot")


def exportar_cliques(link_id: int):
    """Linhas do CSV (cabeçalho primeiro), um clique por linha, hora de Brasília."""
    yield list(_COLS_CSV)
    with _get_users_engine().connect() as conn:
        res = conn.execute(
            text(f"SELECT {', '.join(_COLS_CSV)} FROM encurtador.cliques WHERE link_id = :id ORDER BY ts DESC"),
            {"id": link_id},
        )
        for r in res:
            ts = r[0] if r[0].tzinfo else r[0].replace(tzinfo=timezone.utc)
            yield [ts.astimezone(TZ).strftime("%d/%m/%Y %H:%M:%S"), *r[1:-1], "sim" if r[-1] else "não"]
