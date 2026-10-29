"""
Captura ao vivo das aulas no YouTube: chat e simultâneos, minuto a minuto.

O ETL das aulas (`etl_youtube_analytics.py`) traz a curva de simultâneos depois
que a live acaba, mas o chat não: a API não guarda as mensagens de uma live
encerrada. Este módulo conta as mensagens enquanto a transmissão está no ar e
grava em `youtube_live_curva.chat_msgs`, no mesmo (lançamento, aula, minuto)
que a curva do ETL vai preencher depois. Reações não existem na API — seguem
vindo só do CSV do Studio.

Roda dentro do processo do `scheduler.py`, a cada minuto, e só faz chamada à
API na janela do evento de um lançamento: a cada 5 min procura live no ar no
canal do expert; achou, passa a ler o chat a cada minuto até a live terminar.
O estado (página do chat, contagem por minuto) fica em memória; se o processo
reinicia no meio da live, a contagem é retomada do banco.

Uso manual (um tique, para testar):
    python etl/youtube_live_chat.py
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger
from etl_youtube_analytics import (
    YT_API_BASE, _TZ_BR, _get_access_token, descobrir_aulas, lancamentos_na_janela,
)

logger = get_logger("etl.youtube_chat")

# Tipos que o Studio conta como "mensagem do chat".
_TIPOS_MENSAGEM = {"textMessageEvent", "superChatEvent", "superStickerEvent"}
_BUSCA_LIVE_SEG = 300
_LANCAMENTOS_SEG = 3600

_lancamentos: tuple[float, list] = (0.0, [])
_tokens: dict[str, tuple[str, float]] = {}
_proxima_busca: dict[str, float] = {}
_ao_vivo: dict[str, dict] = {}   # video_id -> estado da live em captura


def _minuto(publicado: str, inicio: datetime) -> int:
    """Segundo (múltiplo de 60) da transmissão em que a mensagem saiu."""
    dt = datetime.fromisoformat(publicado.replace("Z", "+00:00"))
    return max(0, int((dt - inicio).total_seconds()) // 60 * 60)


def contar_mensagens(itens: list[dict], inicio: datetime, contagem: dict[int, int], corte: int) -> set[int]:
    """Soma as mensagens em `contagem` por minuto; devolve os minutos tocados.

    Minutos até `corte` já estão no banco (retomada após reinício) e são
    ignorados — a primeira leitura sem página devolve mensagens antigas, e
    contá-las de novo dobraria esses minutos.
    """
    tocados = set()
    for item in itens:
        snip = item.get("snippet") or {}
        if snip.get("type") not in _TIPOS_MENSAGEM or not snip.get("publishedAt"):
            continue
        seg = _minuto(snip["publishedAt"], inicio)
        if seg <= corte:
            continue
        contagem[seg] = contagem.get(seg, 0) + 1
        tocados.add(seg)
    return tocados


def _token(code: str) -> str:
    tok, expira = _tokens.get(code, ("", 0.0))
    if time.time() < expira:
        return tok
    tok = _get_access_token(code)
    _tokens[code] = (tok, time.time() + 45 * 60)  # access token vale 1h
    return tok


def _lancamentos_da_semana() -> list:
    """Lançamentos cuja janela de aulas inclui hoje; relido de hora em hora."""
    global _lancamentos
    lido_em, lista = _lancamentos
    if time.time() - lido_em > _LANCAMENTOS_SEG:
        hoje = datetime.now(_TZ_BR).date()
        lista = [(code, jan) for code, jan, _periodo in lancamentos_na_janela(hoje) if jan[0] <= hoje <= jan[1]]
        _lancamentos = (time.time(), lista)
    return lista


def _iniciar(code: str, aula_num: int, aula: dict) -> dict:
    """Estado de uma live recém-achada, retomando a contagem que já está no banco."""
    with get_engine().begin() as conn:
        # A página só mostra aula que tem linha em youtube_aulas_stats; o ETL
        # completa os totais depois.
        conn.execute(text("""
            INSERT INTO youtube_aulas_stats (launch_code, video_id, aula_num, titulo, published_at)
            VALUES (:c, :v, :n, :t, :p)
            ON CONFLICT (launch_code, video_id) DO NOTHING
        """), {"c": code, "v": aula["id"], "n": aula_num, "t": aula["label"], "p": aula["inicio"]})
        linhas = conn.execute(text("""
            SELECT posicao_seg, chat_msgs FROM youtube_live_curva
            WHERE launch_code = :c AND aula_num = :n AND chat_msgs > 0
        """), {"c": code, "n": aula_num}).fetchall()
    contagem = {r.posicao_seg: r.chat_msgs for r in linhas}
    logger.info("%s Aula %d no ar (%s) — capturando chat%s", code, aula_num, aula["id"],
                f", retomando {sum(contagem.values())} msgs" if contagem else "")
    return {
        "code": code, "aula_num": aula_num, "video_id": aula["id"], "inicio": aula["inicio"],
        "chat_id": aula["chat_id"], "page": None, "contagem": contagem,
        "corte": max(contagem, default=-1),
    }


def _procurar_live(code: str, janela) -> None:
    if time.time() < _proxima_busca.get(code, 0.0):
        return
    _proxima_busca[code] = time.time() + _BUSCA_LIVE_SEG
    aulas = descobrir_aulas(_token(code), *janela)
    for num, aula in enumerate(aulas, start=1):
        if aula["no_ar"] and aula["id"] not in _ao_vivo:
            _ao_vivo[aula["id"]] = _iniciar(code, num, aula)


def _ler_chat(est: dict, headers: dict) -> set[int]:
    tocados: set[int] = set()
    for _ in range(5):  # até 10 mil mensagens por minuto
        params = {"liveChatId": est["chat_id"], "part": "snippet", "maxResults": 2000}
        if est["page"]:
            params["pageToken"] = est["page"]
        r = requests.get(f"{YT_API_BASE}/liveChat/messages", headers=headers, params=params, timeout=20)
        if r.status_code == 403:
            # Chat desligado ou encerrado: segue só com os simultâneos.
            logger.warning("%s Aula %d: chat indisponível (%s)", est["code"], est["aula_num"], r.text[:200])
            est["chat_id"] = None
            break
        r.raise_for_status()
        data = r.json()
        itens = data.get("items", [])
        est["page"] = data.get("nextPageToken")
        tocados |= contar_mensagens(itens, est["inicio"], est["contagem"], est["corte"])
        if len(itens) < 2000:
            break
    return tocados


def _capturar(est: dict) -> bool:
    """Um minuto de captura. Devolve False quando a live terminou."""
    headers = {"Authorization": f"Bearer {_token(est['code'])}"}
    r = requests.get(f"{YT_API_BASE}/videos", headers=headers,
                     params={"part": "liveStreamingDetails", "id": est["video_id"]}, timeout=20)
    r.raise_for_status()
    itens = r.json().get("items", [])
    det = (itens[0].get("liveStreamingDetails") or {}) if itens else {}
    no_ar = bool(itens) and not det.get("actualEndTime")
    simult = int(det.get("concurrentViewers") or 0)

    tocados = _ler_chat(est, headers) if est["chat_id"] else set()
    agora = _minuto(datetime.now(_TZ_BR).isoformat(), est["inicio"])
    linhas = [{"seg": s, "chat": est["contagem"][s], "simult": 0} for s in tocados if s != agora]
    if no_ar:
        linhas.append({"seg": agora, "chat": est["contagem"].get(agora, 0), "simult": simult})

    if linhas:
        with get_engine().begin() as conn:
            # Simultâneos daqui são uma leitura instantânea, só para a página
            # acompanhar a live: a curva oficial do ETL sobrescreve depois.
            conn.execute(text("""
                INSERT INTO youtube_live_curva (launch_code, aula_num, posicao_seg, simultaneos, media_simult, chat_msgs)
                VALUES (:c, :n, :seg, :simult, :simult, :chat)
                ON CONFLICT (launch_code, aula_num, posicao_seg) DO UPDATE SET
                    chat_msgs    = EXCLUDED.chat_msgs,
                    simultaneos  = GREATEST(youtube_live_curva.simultaneos, EXCLUDED.simultaneos),
                    media_simult = COALESCE(NULLIF(youtube_live_curva.media_simult, 0), EXCLUDED.media_simult)
            """), [{"c": est["code"], "n": est["aula_num"], **l} for l in linhas])

    if not no_ar:
        logger.info("%s Aula %d encerrada — %d mensagens no chat", est["code"], est["aula_num"],
                    sum(est["contagem"].values()))
    return no_ar


def tick() -> list[str]:
    """Um minuto do agendador. Devolve as falhas (texto) sem levantar."""
    erros: list[str] = []
    try:
        semana = _lancamentos_da_semana()
    except Exception as e:
        return [f"lançamentos da semana: {e}"]

    for code, janela in semana:
        try:
            _procurar_live(code, janela)
        except Exception as e:
            erros.append(f"{code}: busca de live: {e}")

    for vid, est in list(_ao_vivo.items()):
        try:
            if not _capturar(est):
                del _ao_vivo[vid]
        except Exception as e:
            erros.append(f"{est['code']} Aula {est['aula_num']}: {e}")
    return erros


if __name__ == "__main__":
    falhas = tick()
    print(f"{len(_ao_vivo)} live(s) em captura; falhas: {falhas or 'nenhuma'}")
    sys.exit(1 if falhas else 0)
