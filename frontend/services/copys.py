"""
frontend/services/copys.py — Análise de Copys: gancho × retenção × CPL × venda × ROAS.

Cruza o texto falado de cada criativo (`ad_transcricoes`) com o que ele gastou e
vendeu, agrupado por família de gancho. Plano em
docs/projetos/PLANO_ANALISE_COPYS.md.

Três regras que não podem ser afrouxadas aqui, cada uma custou um erro real:

1. **Escopo por etapa.** Captação é `[cadastro]` e Pré-Qualificação é
   `[engajamento]`: objetivos diferentes, então CPL não é comparável entre elas.
   Comparar tudo junto produziu "notícia tem CPL de R$ 158, 14x pior" — artefato
   puro (17/09/26).
2. **Só gancho confiável.** `hook_confiavel` é `True` apenas quando a
   transcrição vem do vídeo publicado. Nos `.txt` de filmagem crua o `[00:00]`
   não é o início do anúncio, e o "gancho" seria texto que nunca foi ao ar.
3. **CPA e ROAS, não só CPL.** No PES-SET-26 o ranking por CPL é quase o
   inverso do ranking por CPA: a família com o melhor CPL (R$ 8,68) tem CPA de
   R$ 699, e a de CPL mediano (R$ 10,92) tem CPA de R$ 410 e ROAS 3,96. Mostrar
   CPL sozinho leva a decisão errada.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

# Famílias de gancho. Ordem importa: a primeira que casar vence, então o padrão
# mais específico vem antes. É heurística de partida — a intenção é que vire
# curadoria em `ad_copy_atributos` (origem='humano'), que o regex não sobrescreve.
FAMILIAS: list[tuple[str, re.Pattern]] = [
    ("pergunta \"tá sabendo?\"", re.compile(
        r"ta sabendo|esta sabendo|ce ta sabendo|voce esta sabendo|verdade que", re.I)),
    ("notícia publicada", re.compile(
        r"acaba de ser publicado|saiu noticia|olha so essa noticia|noticia nova", re.I)),
    ("antecipação de edital", re.compile(r"e vem ai|deve sair|previsto", re.I)),
    ("benefício concreto", re.compile(r"folga|salario|ganha|r\$", re.I)),
    ("superlativo", re.compile(r"maior", re.I)),
    ("dor do iniciante", re.compile(r"iniciante|melhor concurso|do zero", re.I)),
]

SQL_GANCHOS = r"""
WITH g AS (
    SELECT upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')) AS ad_code,
           CASE WHEN campaign_name ILIKE '%capta%'  THEN 'Captação'
                WHEN campaign_name ILIKE '%quali%'  THEN 'Pré-Qualificação'
                ELSE 'Outras' END                            AS etapa,
           sum(spend) AS gasto, sum(leads) AS leads,
           sum(impressions) AS impressoes, sum(video_views_3s) AS views_3s,
           sum(video_thruplays) AS thruplays, sum(video_views_100) AS views_100
    FROM   meta_ads_daily
    WHERE  lancamento_codigo = :codigo
      AND  upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')) ~ '^AD[0-9]+$'
    GROUP  BY 1, 2
), h AS (
    SELECT t.ad_code, t.duracao_seg, t.fonte_tipo,
           string_agg(l.texto, ' ' ORDER BY l.ordem) AS gancho
    FROM   ad_transcricoes t
    JOIN   ad_transcricao_linhas l ON l.transcricao_id = t.id
    WHERE  t.lancamento_codigo = :codigo
      AND  t.is_canonica AND t.hook_confiavel
      AND  l.t_ini_seg < 3
    GROUP  BY t.ad_code, t.duracao_seg, t.fonte_tipo
)
SELECT g.etapa, h.ad_code, h.gancho, h.duracao_seg,
       g.gasto, g.leads, g.impressoes, g.views_3s, g.thruplays, g.views_100
FROM   h JOIN g USING (ad_code)
WHERE  g.gasto >= :piso
ORDER  BY g.gasto DESC
"""


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c))


def familia_do_gancho(gancho: str) -> str:
    """Família do gancho pelas 3 primeiras falas. Compara sem acento porque a
    transcrição do Whisper varia ("tá"/"ta", "está"/"esta")."""
    plano = _sem_acento(gancho or "").lower()
    for nome, rx in FAMILIAS:
        if rx.search(plano):
            return nome
    return "outro"


def _linha(nome: str, a: dict) -> dict:
    gasto, leads, vendas = a["gasto"], a["leads"], a["vendas"]
    return {
        "nome": nome,
        "ads": a["ads"],
        "exemplos": a["exemplos"][:3],
        "gasto": gasto,
        "leads": leads,
        "vendas": vendas,
        "faturamento": a["faturamento"],
        "cpl": gasto / leads if leads else 0.0,
        # CPA só existe com venda atribuída. Zero vendas devolve None em vez de
        # 0, senão o anúncio sem venda apareceria como o CPA mais baixo da tabela.
        "cpa": gasto / vendas if vendas else None,
        "roas": a["faturamento"] / gasto if gasto else 0.0,
        "conv_lead_venda": vendas / leads if leads else 0.0,
        "hook_rate": a["views_3s"] / a["impressoes"] if a["impressoes"] else 0.0,
        "hold_rate": a["thruplays"] / a["views_3s"] if a["views_3s"] else 0.0,
        "completion": a["views_100"] / a["views_3s"] if a["views_3s"] else 0.0,
    }


def read_analise_copys(launch_code: str, sales_attr: dict | None,
                       piso_gasto: float = 500.0) -> dict:
    """Confronto por família de gancho, uma tabela por etapa.

    `sales_attr` vem de `_sales_attribution` — usa `por_criativo_por_etapa`, que
    já escopa a venda por etapa. Usar `por_criativo` (global) jogaria a venda da
    Captação em cima do gasto da Pré-Quali e inflaria o ROAS dela."""
    from sqlalchemy import text  # noqa: PLC0415

    from frontend.db import _get_engine  # noqa: PLC0415

    with _get_engine().connect() as conn:
        rows = conn.execute(text(SQL_GANCHOS),
                            {"codigo": launch_code, "piso": piso_gasto}).fetchall()

    vendas_por_etapa = (sales_attr or {}).get("por_criativo_por_etapa") or {}

    etapas: dict[str, dict[str, dict]] = {}
    por_ad: list[dict] = []
    for (etapa, ad_code, gancho, duracao, gasto, leads,
         impressoes, views_3s, thruplays, views_100) in rows:
        if etapa == "Outras":
            continue
        venda = (vendas_por_etapa.get(etapa) or {}).get(ad_code) or {}
        n_vendas = int(venda.get("vendas") or 0)
        receita = float(venda.get("faturamento") or 0.0)
        familia = familia_do_gancho(gancho)

        a = etapas.setdefault(etapa, {}).setdefault(familia, {
            "ads": 0, "gasto": 0.0, "leads": 0, "vendas": 0, "faturamento": 0.0,
            "impressoes": 0, "views_3s": 0, "thruplays": 0, "views_100": 0,
            "exemplos": [],
        })
        a["ads"] += 1
        a["gasto"] += float(gasto or 0)
        a["leads"] += int(leads or 0)
        a["vendas"] += n_vendas
        a["faturamento"] += receita
        a["impressoes"] += int(impressoes or 0)
        a["views_3s"] += int(views_3s or 0)
        a["thruplays"] += int(thruplays or 0)
        a["views_100"] += int(views_100 or 0)
        a["exemplos"].append({"ad_code": ad_code, "gancho": (gancho or "").strip()})

        por_ad.append({
            "etapa": etapa, "ad_code": ad_code, "familia": familia,
            "gancho": (gancho or "").strip(), "duracao_seg": duracao,
            "gasto": float(gasto or 0), "leads": int(leads or 0),
            "vendas": n_vendas, "faturamento": receita,
            "cpl": float(gasto or 0) / int(leads) if leads else 0.0,
            "cpa": float(gasto or 0) / n_vendas if n_vendas else None,
            "roas": receita / float(gasto) if gasto else 0.0,
            "hook_rate": (int(views_3s or 0) / int(impressoes)) if impressoes else 0.0,
            "hold_rate": (int(thruplays or 0) / int(views_3s)) if views_3s else 0.0,
        })

    # Captação primeiro: é a etapa onde CPA/ROAS têm significado de verdade.
    ordem = ["Captação", "Pré-Qualificação"]
    tabelas = []
    for etapa in sorted(etapas, key=lambda e: ordem.index(e) if e in ordem else 99):
        familias = [_linha(n, a) for n, a in etapas[etapa].items()]
        # Ordena por CPA (menor primeiro); quem não vendeu vai pro fim.
        familias.sort(key=lambda f: (f["cpa"] is None, f["cpa"] or 0))
        tabelas.append({
            "etapa": etapa,
            "familias": familias,
            "gasto": sum(f["gasto"] for f in familias),
            "vendas": sum(f["vendas"] for f in familias),
            "faturamento": sum(f["faturamento"] for f in familias),
            "metrica_principal": "CPA" if etapa == "Captação" else "custo/ThruPlay",
        })

    return {
        "tabelas": tabelas,
        "por_ad": sorted(por_ad, key=lambda r: -r["gasto"]),
        "cobertura": _cobertura(launch_code, por_ad),
        "piso_gasto": piso_gasto,
    }


def _cobertura(launch_code: str, por_ad: list[dict]) -> dict:
    """Quanto da verba a análise realmente cobre.

    A página precisa dizer isso na cara: sem esse número, um pódio decidido por
    poucos anúncios parece representar o lançamento inteiro."""
    from sqlalchemy import text  # noqa: PLC0415

    from frontend.db import _get_engine  # noqa: PLC0415

    sql = r"""
        SELECT sum(v) FROM (
            SELECT spend AS v FROM meta_ads_daily WHERE lancamento_codigo = :c
            UNION ALL
            SELECT cost      FROM google_ads_daily WHERE lancamento_codigo = :c
        ) u
    """
    with _get_engine().connect() as conn:
        total = float(conn.execute(text(sql), {"c": launch_code}).scalar_one() or 0)
    analisado = sum(r["gasto"] for r in por_ad)
    return {
        "gasto_analisado": analisado,
        "gasto_total": total,
        "pct": analisado / total if total else 0.0,
        "ads": len(por_ad),
    }


def maior_contraste(tabelas: list[dict]) -> dict | None:
    """A leitura que a página existe para dar: onde CPL e CPA discordam.

    No PES-SET-26 a família de melhor CPL tem CPA 70% pior que a melhor de CPA —
    otimizar por CPL escolheria o gancho errado."""
    captacao = next((t for t in tabelas if t["etapa"] == "Captação"), None)
    if not captacao:
        return None
    com_venda = [f for f in captacao["familias"] if f["cpa"]]
    if len(com_venda) < 2:
        return None
    melhor_cpl = min(com_venda, key=lambda f: f["cpl"] or float("inf"))
    melhor_cpa = min(com_venda, key=lambda f: f["cpa"])
    if melhor_cpl["nome"] == melhor_cpa["nome"]:
        return {"concordam": True, "familia": melhor_cpa["nome"]}
    return {
        "concordam": False,
        "por_cpl": melhor_cpl,
        "por_cpa": melhor_cpa,
        "penalidade_cpa": (melhor_cpl["cpa"] / melhor_cpa["cpa"] - 1),
    }


def enriquecer(dados: dict) -> dict:
    dados["contraste"] = maior_contraste(dados.get("tabelas") or [])
    return dados


SQL_CURVA = r"""
WITH g AS (
    SELECT upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')) AS ad_code,
           sum(spend) AS gasto, sum(video_views_3s) AS v3,
           sum(video_views_25) AS q25, sum(video_views_50) AS q50,
           sum(video_views_75) AS q75, sum(video_views_100) AS q100
    FROM   meta_ads_daily
    WHERE  lancamento_codigo = :codigo
      AND  campaign_name ILIKE '%capta%'
      AND  upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')) ~ '^AD[0-9]+$'
    GROUP  BY 1
    HAVING sum(video_views_3s) > 1000 AND sum(spend) >= :piso
)
SELECT t.ad_code, t.id, t.duracao_seg,
       g.gasto, g.v3, g.q25, g.q50, g.q75, g.q100
FROM   ad_transcricoes t JOIN g USING (ad_code)
WHERE  t.lancamento_codigo = :codigo AND t.is_canonica AND t.hook_confiavel
ORDER  BY g.gasto DESC
"""


def read_curva_retencao(launch_code: str, sales_attr: dict | None,
                        piso_gasto: float = 2000.0) -> dict:
    """Curva de retenção de cada criativo, com o que é falado em cada quartil.

    Normaliza pelos views de 3s (não por impressões): o interesse é o que
    acontece *depois* que a pessoa parou, e é o mesmo denominador do hold_rate.

    Duas coisas que a leitura desta seção precisa deixar claras, porque os
    dados do PES-SET-26 contrariam a intuição:

    1. **A maior queda é sempre o Q1**, em todos os anúncios (71% a 81%).
       Perguntar "qual quartil perde mais" não tem resposta útil — a perda é
       toda na entrada. O que informa é comparar o mesmo quartil *entre*
       anúncios.
    2. **Retenção não prevê CPA.** Correlação de +0,13 entre retenção a 100% e
       CPA em 13 criativos de Captação — perto de zero e no sinal errado. Os
       três de melhor retenção têm CPA acima da mediana. Serve para *ler* o
       criativo, não para decidir verba.
    """
    from sqlalchemy import text  # noqa: PLC0415

    from frontend.db import _get_engine  # noqa: PLC0415

    vendas = ((sales_attr or {}).get("por_criativo_por_etapa") or {}).get("Captação") or {}

    with _get_engine().connect() as conn:
        linhas = conn.execute(text(SQL_CURVA),
                              {"codigo": launch_code, "piso": piso_gasto}).fetchall()
        if not linhas:
            return {"ads": [], "correlacao": None, "piso_gasto": piso_gasto}

        falas = {}
        for tid in {r[1] for r in linhas}:
            falas[tid] = {
                q: txt for q, txt in conn.execute(text(
                    "SELECT quartil, string_agg(texto, ' ' ORDER BY ordem)"
                    " FROM ad_transcricao_linhas WHERE transcricao_id = :t"
                    " GROUP BY quartil"), {"t": tid}).fetchall()
            }

    ads = []
    for ad_code, tid, duracao, gasto, v3, q25, q50, q75, q100 in linhas:
        ret = [q25 / v3, q50 / v3, q75 / v3, q100 / v3]
        n_vendas = int((vendas.get(ad_code) or {}).get("vendas") or 0)
        ads.append({
            "ad_code": ad_code,
            "duracao_seg": duracao,
            "gasto": float(gasto or 0),
            "vendas": n_vendas,
            "cpa": float(gasto) / n_vendas if n_vendas else None,
            "retencao": [{"quartil": i + 1,
                          "pct": ret[i],
                          # Segundo aproximado em que o quartil termina — é o que
                          # liga a curva à fala, já que o Meta só dá os 4 marcos.
                          "ate_seg": round((duracao or 0) * (i + 1) / 4),
                          "fala": (falas.get(tid, {}).get(i + 1) or "").strip()}
                         for i in range(4)],
            "queda_entrada": 1 - ret[0],
        })

    # Correlacao CPA x retencao a 100%, calculada na propria pagina pra o numero
    # nunca ficar desatualizado em relacao aos dados exibidos.
    amostra = [(a["cpa"], a["retencao"][3]["pct"]) for a in ads if a["cpa"]]
    correlacao = None
    if len(amostra) >= 4:
        mc = sum(x for x, _ in amostra) / len(amostra)
        mr = sum(y for _, y in amostra) / len(amostra)
        num = sum((x - mc) * (y - mr) for x, y in amostra)
        den = ((sum((x - mc) ** 2 for x, _ in amostra)
                * sum((y - mr) ** 2 for _, y in amostra)) ** 0.5)
        if den:
            correlacao = {"r": num / den, "n": len(amostra)}

    return {"ads": ads, "correlacao": correlacao, "piso_gasto": piso_gasto}


def read_copys_page(launch: Any, sales_attr: dict | None) -> dict:
    if not launch:
        return {"tabelas": [], "por_ad": [], "cobertura": None,
                "contraste": None, "curva": None}
    dados = enriquecer(read_analise_copys(launch.code, sales_attr))
    try:
        dados["curva"] = read_curva_retencao(launch.code, sales_attr)
    except Exception:  # a curva é complementar; não pode derrubar a página
        dados["curva"] = None
    return dados
