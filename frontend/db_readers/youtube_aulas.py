"""
frontend/db_readers/youtube_aulas.py — Leitura e análise das aulas ao vivo.

A tabela `youtube_live_curva` guarda a transmissão minuto a minuto (espectadores
simultâneos, mensagens de chat, reações). O card do /debriefing mostra só o
resumo; aqui ficam as leituras que precisam da curva inteira: em que minuto a
audiência bateu o pico, onde ela caiu mais, como cada aula se compara à
anterior e quanto o público interagiu por pessoa.

Nada aqui depende da API do YouTube — a curva vem do relatório pós-transmissão
exportado no Studio (`etl/etl_youtube_csv.py`).
"""
from __future__ import annotations

from sqlalchemy import text

from frontend.db import _get_engine
from logger import get_logger

logger = get_logger("db")

# Janela usada para achar "onde a audiência caiu mais". 5 min é curto o
# bastante para apontar um momento da aula e longo o bastante para não
# capturar oscilação de um minuto só.
JANELA_QUEDA_MIN = 5


def _pct(parte: float, total: float) -> float:
    return round(parte / total * 100, 1) if total else 0.0


def _marcos(curva: list[dict], pico: int, passo: int = 15) -> list[dict]:
    """Audiência a cada `passo` minutos, em % do pico — a régua que permite
    comparar aulas de durações diferentes na mesma escala."""
    if not curva or not pico:
        return []
    por_min = {p["min"]: p for p in curva}
    fim = curva[-1]["min"]
    marcos = []
    for m in range(0, fim + 1, passo):
        ponto = por_min.get(m)
        if ponto is None:  # minuto ausente no export: pega o mais próximo antes
            anteriores = [p for p in curva if p["min"] <= m]
            ponto = anteriores[-1] if anteriores else None
        if ponto:
            marcos.append({
                "min": m,
                "simultaneos": ponto["simultaneos"],
                "pct_pico": _pct(ponto["simultaneos"], pico),
            })
    return marcos


def _maiores_quedas(curva: list[dict], pico: int, top: int = 3) -> list[dict]:
    """Janelas de `JANELA_QUEDA_MIN` com maior perda de audiência.

    Só considera janelas depois do pico: antes dele a audiência ainda está
    entrando, e uma queda ali é ruído, não abandono.
    """
    if len(curva) <= JANELA_QUEDA_MIN or not pico:
        return []
    idx_pico = max(range(len(curva)), key=lambda i: curva[i]["simultaneos"])
    quedas = []
    for i in range(idx_pico, len(curva) - JANELA_QUEDA_MIN):
        ini, fim = curva[i], curva[i + JANELA_QUEDA_MIN]
        perda = ini["simultaneos"] - fim["simultaneos"]
        if perda > 0:
            quedas.append({
                "min_ini":  ini["min"],
                "min_fim":  fim["min"],
                "de":       ini["simultaneos"],
                "para":     fim["simultaneos"],
                "perda":    perda,
                "pct_pico": _pct(perda, pico),
            })
    quedas.sort(key=lambda q: q["perda"], reverse=True)

    # Descarta janelas sobrepostas: duas leituras do mesmo tombo não são
    # dois momentos diferentes da aula.
    escolhidas: list[dict] = []
    for q in quedas:
        if all(q["min_fim"] <= e["min_ini"] or q["min_ini"] >= e["min_fim"] for e in escolhidas):
            escolhidas.append(q)
        if len(escolhidas) == top:
            break
    return escolhidas


def _analisar(aula: dict) -> dict:
    """Deriva da curva tudo que o resumo por aula não carrega."""
    curva = aula["curva"]
    simult = [p["simultaneos"] for p in curva]
    pico = max(simult) if simult else 0
    idx_pico = simult.index(pico) if pico else 0

    chat_por_min = [p["chat"] for p in curva]
    rea_por_min = [p["reacoes"] for p in curva]
    chat_total = sum(chat_por_min)
    rea_total = sum(rea_por_min)

    # Média de simultâneos ao longo da transmissão: separa a aula que teve um
    # pico e esvaziou da que segurou audiência o tempo todo.
    media = round(sum(simult) / len(simult)) if simult else 0
    fim = simult[-1] if simult else 0

    aula.update({
        "pico":             pico,
        "min_pico":         curva[idx_pico]["min"] if curva else 0,
        "fim":              fim,
        "media_simult":     media,
        "pct_media_pico":   _pct(media, pico),
        "retencao_pct":     _pct(fim, pico),
        "duracao_min":      curva[-1]["min"] if curva else 0,
        "chat":             chat_total,
        "reacoes":          rea_total,
        # Interação por pessoa: o volume bruto premia a aula mais cheia.
        "chat_por_pessoa":  round(chat_total / pico, 1) if pico else 0.0,
        "rea_por_pessoa":   round(rea_total / pico, 1) if pico else 0.0,
        "min_chat_pico":    curva[chat_por_min.index(max(chat_por_min))]["min"] if chat_total else 0,
        "chat_pico":        max(chat_por_min) if chat_total else 0,
        "min_rea_pico":     curva[rea_por_min.index(max(rea_por_min))]["min"] if rea_total else 0,
        "rea_pico":         max(rea_por_min) if rea_total else 0,
        "marcos":           _marcos(curva, pico),
        "quedas":           _maiores_quedas(curva, pico),
    })
    return aula


# Como cada corte do relatório de retenção aparece na tela. A ordem é a da
# leitura: primeiro o total, depois os cortes que se comparam entre si.
SEGMENTOS = [
    ("todos",            "Todos",                  "#334155"),
    ("inscrito",         "Inscritos",              "#16a34a"),
    ("nao_inscrito",     "Não inscritos",          "#dc2626"),
    ("recorrente",       "Espectadores recorrentes", "#2563eb"),
    ("novo",             "Espectadores novos",     "#f59e0b"),
    ("frequente",        "Público frequente",      "#7c3aed"),
    ("casual",           "Público casual",         "#0891b2"),
    ("trafego_organico", "Tráfego orgânico",       "#64748b"),
    ("trafego_pago",     "Tráfego pago (anúncios)", "#db2777"),
]


def read_retencao_video(launch_code: str) -> dict:
    """Retenção por posição do vídeo (0-100%) e atividade de início/parada.

    Vem do relatório "Retenção de público" do Studio, que mede o **vídeo**
    (replay incluído) e não a transmissão — são populações diferentes: na Aula
    3 do PI-AGO-26 esse relatório conta menos visualizações do que o pico
    simultâneo que a live teve. Por isso vive numa seção separada da curva
    ao vivo, nunca somado a ela.
    """
    vazio = {"aulas": [], "segmentos": [], "tem_pago": False}
    if not launch_code:
        return vazio

    try:
        with _get_engine().connect() as conn:
            ret = conn.execute(
                text("""
                    SELECT aula_num, segmento, posicao_pct, retencao_pct
                    FROM youtube_video_retencao
                    WHERE launch_code = :code
                    ORDER BY aula_num, segmento, posicao_pct
                """),
                {"code": launch_code},
            ).fetchall()
            ativ = conn.execute(
                text("""
                    SELECT aula_num, posicao_pct, comecaram, pararam, vezes_assistido
                    FROM youtube_video_atividade
                    WHERE launch_code = :code
                    ORDER BY aula_num, posicao_pct
                """),
                {"code": launch_code},
            ).fetchall()
            base = conn.execute(
                text("""
                    SELECT aula_num, titulo, visualizacoes_video, impressoes, ctr_thumb,
                           periodo_ini, periodo_fim, retencao_ini, retencao_fim,
                           views_periodo, watch_periodo_h
                    FROM youtube_aulas_stats
                    WHERE launch_code = :code
                    ORDER BY aula_num
                """),
                {"code": launch_code},
            ).fetchall()
    except Exception as e:
        logger.warning("read_retencao_video falhou para %s: %s", launch_code, e)
        return vazio

    if not ret:
        return vazio

    curvas: dict[int, dict[str, list]] = {}
    for r in ret:
        curvas.setdefault(r.aula_num, {}).setdefault(r.segmento, []).append(
            {"pos": r.posicao_pct, "ret": float(r.retencao_pct or 0)}
        )

    atividades: dict[int, list[dict]] = {}
    for r in ativ:
        atividades.setdefault(r.aula_num, []).append({
            "pos":       r.posicao_pct,
            "comecaram": r.comecaram or 0,
            "pararam":   r.pararam or 0,
            "vezes":     r.vezes_assistido or 0,
        })

    aulas = []
    for b in base:
        segs = curvas.get(b.aula_num)
        if not segs:
            continue
        a = atividades.get(b.aula_num, [])
        # Onde mais gente abandonou: a posição não é minuto, é % do vídeo.
        top_saidas = sorted(a, key=lambda p: p["pararam"], reverse=True)[:3] if a else []
        aulas.append({
            "aula_num":     b.aula_num,
            "titulo":       b.titulo or f"Aula {b.aula_num}",
            "views":        b.visualizacoes_video or 0,
            "impressoes":   b.impressoes or 0,
            "ctr_thumb":    float(b.ctr_thumb or 0),
            "periodo_ini":  b.periodo_ini,
            "periodo_fim":  b.periodo_fim,
            "retencao_ini": b.retencao_ini,
            "retencao_fim": b.retencao_fim,
            "views_periodo": b.views_periodo or 0,
            "watch_periodo_h": float(b.watch_periodo_h or 0),
            "curvas":       segs,
            "media_por_segmento": {
                s: round(sum(p["ret"] for p in pts) / len(pts), 1) for s, pts in segs.items() if pts
            },
            "ret_50":       next((p["ret"] for p in segs.get("todos", []) if p["pos"] == 50), 0.0),
            "top_saidas":   [{**p, "pct_views": _pct(p["pararam"], b.visualizacoes_video or 0)} for p in top_saidas],
        })

    presentes = {s for a in aulas for s in a["curvas"]}
    segmentos = [
        {"chave": k, "label": lbl, "cor": cor}
        for k, lbl, cor in SEGMENTOS if k in presentes
    ]
    return {
        "aulas": aulas,
        "segmentos": segmentos,
        # Payload do gráfico: só o que o JS usa. As linhas de `aulas` carregam
        # datas, e `tojson` não serializa date.
        "curvas_js": [{"aula_num": a["aula_num"], "curvas": a["curvas"]} for a in aulas],
        # Se o Studio não trouxe nenhuma linha de tráfego pago, nenhuma view do
        # vídeo veio de anúncio — vale dizer isso na tela, não deixar em branco.
        "tem_pago": "trafego_pago" in presentes,
    }


def read_aulas_ao_vivo(launch_code: str) -> dict:
    """Devolve {aulas: [...], totais: {...}} para a página /aulas-ao-vivo."""
    vazio = {"aulas": [], "totais": {}}
    if not launch_code:
        return vazio

    try:
        with _get_engine().connect() as conn:
            base = conn.execute(
                text("""
                    SELECT aula_num, video_id, titulo, fonte
                    FROM youtube_aulas_stats
                    WHERE launch_code = :code
                    ORDER BY aula_num NULLS LAST, video_id
                """),
                {"code": launch_code},
            ).fetchall()

            pontos = conn.execute(
                text("""
                    SELECT aula_num, posicao_seg, simultaneos, chat_msgs, reacoes
                    FROM youtube_live_curva
                    WHERE launch_code = :code
                    ORDER BY aula_num, posicao_seg
                """),
                {"code": launch_code},
            ).fetchall()
    except Exception as e:
        logger.warning("read_aulas_ao_vivo falhou para %s: %s", launch_code, e)
        return vazio

    curvas: dict[int, list[dict]] = {}
    for p in pontos:
        curvas.setdefault(p.aula_num, []).append({
            "min":         int((p.posicao_seg or 0) / 60),
            "simultaneos": p.simultaneos or 0,
            "chat":        p.chat_msgs or 0,
            "reacoes":     p.reacoes or 0,
        })

    aulas = []
    for r in base:
        curva = curvas.get(r.aula_num or 0)
        if not curva:
            continue  # sem curva não há o que esta página mostre
        video_id = r.video_id or ""
        real = bool(video_id) and not video_id.startswith("manual-")
        aulas.append(_analisar({
            "aula_num": r.aula_num or 0,
            "titulo":   r.titulo or f"Aula {r.aula_num}",
            "video_id": video_id,
            "fonte":    r.fonte or "api",
            "url":      f"https://www.youtube.com/watch?v={video_id}" if real else None,
            "thumb":    f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg" if real else None,
            "thumb_alt": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg" if real else None,
            "curva":    curva,
        }))

    if not aulas:
        return vazio

    # Comparação com a aula anterior: a queda entre aulas é a leitura que
    # mais importa aqui, e ela não existe dentro de uma aula só.
    anterior = None
    for a in aulas:
        if anterior:
            a["delta_pico"] = a["pico"] - anterior["pico"]
            a["delta_pico_pct"] = _pct(a["pico"] - anterior["pico"], anterior["pico"])
        else:
            a["delta_pico"] = None
            a["delta_pico_pct"] = None
        anterior = a

    primeira, ultima = aulas[0], aulas[-1]
    com_pico = [a for a in aulas if a["pico"] > 0]
    totais = {
        "qtd_aulas":      len(aulas),
        "pico_max":       max(a["pico"] for a in aulas),
        "aula_pico_max":  max(aulas, key=lambda a: a["pico"])["aula_num"],
        "chat_total":     sum(a["chat"] for a in aulas),
        "reacoes_total":  sum(a["reacoes"] for a in aulas),
        "minutos_total":  sum(a["duracao_min"] for a in aulas),
        "retencao_media": round(sum(a["retencao_pct"] for a in com_pico) / len(com_pico), 1) if com_pico else 0.0,
        "queda_1_ultima": _pct(ultima["pico"] - primeira["pico"], primeira["pico"]),
        "fonte_manual":   any(a["fonte"] == "manual" for a in aulas),
    }
    return {"aulas": aulas, "totais": totais}
