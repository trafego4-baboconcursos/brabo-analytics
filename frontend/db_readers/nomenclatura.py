"""
frontend/db_readers/nomenclatura.py — Classificação de campanhas pelo nome.

Traduz o nome de uma campanha (``[MA][CAPTAÇÃO][QUENTE][PRINCIPAL] ...``) em
etapa, temperatura, bucket e segmento. Meta e Google seguem a mesma convenção de
colchetes, mas não os mesmos rótulos: por isso os mapas de etapa e temperatura
são separados por plataforma, enquanto bucket e modificador — que sempre foram
iguais nos dois lados — vivem num mapa único.

Este módulo não importa nenhum outro reader de propósito: ele é a folha que
``ads_meta``, ``ads_google`` e ``sales`` compartilham. Enquanto a classificação
morava dentro de ``ads_meta``, ``sales`` precisava importá-la e ``ads_meta``
precisava de ``read_vendas`` de volta — um ciclo que só se sustentava com
imports adiados dentro das funções.
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


def categorizar_campanha_meta(camp: str, legacy: bool = False) -> tuple[str, str, str, str]:
    """``(etapa, temperatura, bucket, segmento)`` de uma campanha do Meta Ads."""
    camp = str(camp).lower()

    etapa = _primeiro_match(camp, ETAPA_MAP_META, entre_colchetes=True) or "Outros"
    if etapa == "Outros" and legacy:
        # Convenção antiga (BV-25): o que está entre colchetes é o OBJETIVO da
        # campanha ("[M] [CADASTRO] Captação INSS ... - BV-25"), e a etapa vem
        # solta no meio do nome. Só age quando o match normal falhou, então não
        # muda a classificação de nenhuma campanha que já resolve hoje.
        etapa = _primeiro_match(camp, ETAPA_MAP_META, entre_colchetes=False) or "Outros"

    temp = _primeiro_match(camp, TEMPERATURA_MAP_META, entre_colchetes=True) or "Outros"
    bucket = _primeiro_match(camp, BUCKET_MAP, entre_colchetes=True) or "Outros"
    modifier = _primeiro_match(camp, MODIFIER_MAP, entre_colchetes=True)

    return etapa, temp, bucket, _montar_segmento(temp, bucket, modifier)


def categorizar_campanha_google(camp: str) -> tuple[str, str, str]:
    """``(etapa, temperatura, segmento)`` de uma campanha do Google Ads."""
    camp = str(camp).lower()

    etapa = _primeiro_match(camp, ETAPA_MAP_GOOGLE, entre_colchetes=False) or "Outros"

    # O Google aceita também a forma invertida "]quente[", vinda de nomes em que
    # o colchete de abertura ficou grudado no token anterior.
    temp = "Outros"
    for chave, rotulo in TEMPERATURA_MAP_GOOGLE.items():
        if f"[{chave}]" in camp or f"]{chave}[" in camp:
            temp = rotulo
            break

    bucket = _primeiro_match(camp, BUCKET_MAP, entre_colchetes=True) or "Outros"
    modifier = _primeiro_match(camp, MODIFIER_MAP, entre_colchetes=True)

    return etapa, temp, _montar_segmento(temp, bucket, modifier)
