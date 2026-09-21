"""
src/nomenclatura.py — Classificação de campanhas pelo nome.

Traduz o nome de uma campanha (``[MA][CAPTAÇÃO][QUENTE][PRINCIPAL] ...``) em
etapa, temperatura, bucket e segmento. Meta e Google seguem a mesma convenção de
colchetes, mas não os mesmos rótulos: por isso os mapas de etapa e temperatura
são separados por plataforma, enquanto bucket e modificador — que sempre foram
iguais nos dois lados — vivem num mapa único.

Este módulo não importa nada do projeto de propósito: ele é a folha que o ETL e
os readers compartilham. Enquanto a classificação morava dentro de ``ads_meta``,
``sales`` precisava importá-la e ``ads_meta`` precisava de ``read_vendas`` de
volta — um ciclo que só se sustentava com imports adiados dentro das funções.

Vive em ``src/`` (e não mais em ``frontend/db_readers/``) desde 21/09/26, quando
o ETL passou a gravar ``etapa``/``temperatura``/``segmento`` na escrita: os dois
lados precisam da mesma função, e ETL não deve importar de ``frontend/``.
``frontend/db_readers/nomenclatura.py`` continua existindo como re-export.
"""
from __future__ import annotations

# ── Etapa do funil ─────────────────────────────────────────────────────────────
# Meta casa a chave entre colchetes ("[aula 1]"); Google casa como substring,
# então aqui uma chave mais curta ("aula") cobre "aula 1".."aula 4".
ETAPA_MAP_META = {
    "pré-qualificação": "Pré-Qualificação", "pre-qualificacao": "Pré-Qualificação",
    "pré-quali": "Pré-Qualificação", "pre-quali": "Pré-Qualificação",
    "captação": "Captação", "captacao": "Captação", "capta": "Captação",
    "lembrete": "Lembrete",
    "depoimento": "Depoimento", "depoimentos": "Depoimento",
    "replay aulas": "Replay", "replay": "Replay",  # deve vir antes de aula para [replay][aula N] → Replay
    # convenção real é um colchete só ("[replay aula 2]"), não "[replay][aula 2]"
    # separados — sem essas chaves específicas, o match exato de "[replay]"
    # nunca bate e o gasto cai inteiro em "Outros".
    "replay aula 1": "Replay", "replay aula 2": "Replay",
    "replay aula 3": "Replay", "replay aula 4": "Replay",
    "aulas no ar": "Aulas no Ar", "aulas-no-ar": "Aulas no Ar",
    "aula 1": "Aulas no Ar", "aula 2": "Aulas no Ar", "aula 3": "Aulas no Ar", "aula 4": "Aulas no Ar",
    "matrículas abertas": "Matrículas Abertas", "matriculas abertas": "Matrículas Abertas",
    "matrículas": "Matrículas Abertas", "matriculas": "Matrículas Abertas",
}

ETAPA_MAP_GOOGLE = {
    "pré-qualificação": "Pré-Qualificação", "pre-qualificacao": "Pré-Qualificação",
    "pré-quali": "Pré-Qualificação", "pre-quali": "Pré-Qualificação",
    "captação": "Captação", "captacao": "Captação", "capta": "Captação",
    "lembrete": "Lembrete",
    "depoimento": "Depoimento",
    "replay": "Replay",  # deve vir antes de aula para [replay aula N] → Replay
    "aulas no ar": "Aulas no Ar", "aulas-no-ar": "Aulas no Ar",
    "aula": "Aulas no Ar",  # cobre aula 1/2/3/4 sem replay
    "matrículas abertas": "Matrículas Abertas", "matriculas abertas": "Matrículas Abertas",
    "matrículas": "Matrículas Abertas", "matriculas": "Matrículas Abertas",
    "performance max": "Performance Max", "pmax": "Performance Max",
}

# ── Temperatura do público ─────────────────────────────────────────────────────
# Só o Meta tem campanha nomeada "lookalike" (que é público frio); no Google o
# equivalente já vem escrito como "frio".
# "aluno" vem antes de "quente" de propósito: na Black o público é Aluno ou
# Super Quente, e "super quente" casaria em "quente" se a ordem fosse outra —
# jogando os dois públicos na mesma linha. Dict preserva ordem de inserção, e
# `_primeiro_match` devolve o primeiro que casar.
TEMPERATURA_MAP_META = {
    "aluno": "Aluno", "alunos": "Aluno",
    "quente": "Quente", "frio": "Frio", "específico": "Específico", "especifico": "Específico",
    "lookalike": "Frio",
}

TEMPERATURA_MAP_GOOGLE = {
    "aluno": "Aluno", "alunos": "Aluno",
    "quente": "Quente", "frio": "Frio", "específico": "Específico", "especifico": "Específico",
}

# ── Bucket e modificador (iguais nas duas plataformas) ─────────────────────────
BUCKET_MAP = {
    "principal": "Principal", "potencial": "Potencial", "reels": "Reels",
    "imagem": "Imagem", "search": "Search", "p-max": "P-Max",
    "shorts": "Shorts",
    "novos-ads": "Novos Ads", "novos_ads": "Novos Ads",
}

MODIFIER_MAP = {
    "otimizada": "otimizada", "teste": "teste",
    "melhores-ads": "melhores ads", "new-ads": "new ads",
}

# ── Perfil BLACK (Black Vitálicia) ─────────────────────────────────────────────
# A Black é um funil diferente do lançamento normal (ver ESTUDO_CAMPANHAS_BV-25 e
# PLANEJAMENTO_BV-26): tem etapa Aquecimento (que não existe no normal), públicos
# Aluno / Super Quente / Novo (em vez de Quente / Frio / Específico) e formatos
# Volume / Carrossel / Trio. Forçar isso no vocabulário normal joga tudo em
# "Outros" (BV-25) ou contamina o mapa global. Por isso um perfil próprio,
# escolhido pelo código do lançamento (BV-*), sem tocar no que roda hoje.
#
# Cobre as DUAS grafias da Black: o BV-25, cuja etapa vinha no OBJETIVO
# ([CADASTRO]=Captação, [ENGAJAMENTO]=Aquecimento, [RECONHECIMENTO]=Lembrete,
# [VENDAS]=Matrículas, [TRÁFEGO]/Base Forte=Aquecimento), e o BV-26, que já nomeia
# a etapa direto ([aquecimento][captação][lembrete][matrículas]).
ETAPA_MAP_BLACK = {
    "aquecimento": "Aquecimento", "engajamento": "Aquecimento",
    "base forte": "Aquecimento", "tráfego": "Aquecimento", "trafego": "Aquecimento",
    "captação": "Captação", "captacao": "Captação", "capta": "Captação", "cadastro": "Captação",
    "lembrete": "Lembrete", "reconhecimento": "Lembrete",
    "matrículas abertas": "Matrículas Abertas", "matriculas abertas": "Matrículas Abertas",
    "matrículas": "Matrículas Abertas", "matriculas": "Matrículas Abertas",
    "vendas": "Matrículas Abertas", "venda": "Matrículas Abertas",
}

# "super quente" ANTES de "quente": no fallback por substring, "quente" casaria
# dentro de "super quente" e fundiria os dois públicos. Em colchete exato não há
# colisão ([super quente] != [quente]), mas a ordem protege o modo substring.
TEMPERATURA_MAP_BLACK = {
    "super quentes": "Super Quente", "super quente": "Super Quente",
    "aluno": "Aluno", "alunos": "Aluno",
    "novos": "Novo", "novo": "Novo",
    "quente": "Quente", "frio": "Frio",
}

BUCKET_MAP_BLACK = {
    **BUCKET_MAP,
    "volume": "Volume", "trio": "Trio", "carrossel": "Carrossel", "feed": "Feed",
}


def _is_black(launch_code: str | None) -> bool:
    """A Black usa o perfil próprio de classificação. Detecção pelo código do
    lançamento (BV-25, BV-26, …) — não confundir com o flag de código de anúncio
    legado, que é só BV-25."""
    return str(launch_code or "").strip().upper().startswith("BV")


def _primeiro_match(camp: str, mapa: dict[str, str], *, entre_colchetes: bool) -> str | None:
    """Primeiro rótulo de ``mapa`` cuja chave aparece em ``camp``.

    A ordem de inserção do mapa é significativa: "replay" precisa ser testado
    antes de "aula" para que ``[replay][aula 2]`` classifique como Replay.
    """
    for chave, rotulo in mapa.items():
        if (f"[{chave}]" in camp) if entre_colchetes else (chave in camp):
            return rotulo
    return None


def _montar_segmento(temp: str, bucket: str, modifier: str | None) -> str:
    partes = [p for p in (temp if temp != "Outros" else None,
                          bucket if bucket != "Outros" else None) if p]
    segmento = " ".join(partes) if partes else "Outros"
    return f"{segmento} ({modifier})" if modifier else segmento


def categorizar_campanha_meta(camp: str, launch_code: str | None = None,
                              legacy: bool = False) -> tuple[str, str, str, str]:
    """``(etapa, temperatura, bucket, segmento)`` de uma campanha do Meta Ads.

    Lançamento Black (``launch_code`` começa com BV) usa o perfil próprio, com
    fallback por substring (o BV-25 traz etapa/público fora dos colchetes; o
    BV-26 dentro). Lançamento normal fica idêntico ao de antes — só cai no
    fallback por substring se ``legacy=True`` (convenção antiga).
    """
    camp = str(camp).lower()
    black = _is_black(launch_code)
    etapa_map = ETAPA_MAP_BLACK if black else ETAPA_MAP_META
    temp_map = TEMPERATURA_MAP_BLACK if black else TEMPERATURA_MAP_META
    bucket_map = BUCKET_MAP_BLACK if black else BUCKET_MAP

    etapa = _primeiro_match(camp, etapa_map, entre_colchetes=True) or "Outros"
    # etapa fora dos colchetes: comportamento antigo do `legacy` (BV-25 traz a
    # etapa solta) — mantido, mais o perfil Black.
    if etapa == "Outros" and (black or legacy):
        etapa = _primeiro_match(camp, etapa_map, entre_colchetes=False) or "Outros"

    temp = _primeiro_match(camp, temp_map, entre_colchetes=True) or "Outros"
    bucket = _primeiro_match(camp, bucket_map, entre_colchetes=True) or "Outros"
    # Fallback por substring de temperatura/bucket é EXCLUSIVO do perfil Black —
    # o `legacy` normal nunca fez isso, e ampliar quebraria a classificação de
    # lançamentos antigos que já resolvem hoje.
    if black:
        if temp == "Outros":
            temp = _primeiro_match(camp, temp_map, entre_colchetes=False) or "Outros"
        if bucket == "Outros":
            bucket = _primeiro_match(camp, bucket_map, entre_colchetes=False) or "Outros"

    modifier = _primeiro_match(camp, MODIFIER_MAP, entre_colchetes=True)

    return etapa, temp, bucket, _montar_segmento(temp, bucket, modifier)


def categorizar_campanha_google(camp: str, launch_code: str | None = None) -> tuple[str, str, str]:
    """``(etapa, temperatura, segmento)`` de uma campanha do Google Ads."""
    camp = str(camp).lower()
    black = _is_black(launch_code)
    etapa_map = ETAPA_MAP_BLACK if black else ETAPA_MAP_GOOGLE
    temp_map = TEMPERATURA_MAP_BLACK if black else TEMPERATURA_MAP_GOOGLE
    bucket_map = BUCKET_MAP_BLACK if black else BUCKET_MAP

    etapa = _primeiro_match(camp, etapa_map, entre_colchetes=False) or "Outros"

    # O Google aceita também a forma invertida "]quente[", vinda de nomes em que
    # o colchete de abertura ficou grudado no token anterior. Na Black, também
    # casa por substring (nome do BV-25 traz o público solto).
    temp = "Outros"
    for chave, rotulo in temp_map.items():
        if f"[{chave}]" in camp or f"]{chave}[" in camp or (black and chave in camp):
            temp = rotulo
            break

    bucket = _primeiro_match(camp, bucket_map, entre_colchetes=True) or "Outros"
    if black and bucket == "Outros":
        bucket = _primeiro_match(camp, bucket_map, entre_colchetes=False) or "Outros"
    modifier = _primeiro_match(camp, MODIFIER_MAP, entre_colchetes=True)

    return etapa, temp, _montar_segmento(temp, bucket, modifier)
