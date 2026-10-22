"""Constantes compartilhadas pelos leitores em frontend/db_readers."""
from __future__ import annotations

ETAPAS_ORDEM: list[str] = [
    "Pré-Qualificação",
    "Captação",
    "Lembrete",
    "Aulas no Ar",
    "Replay",
    "Matrículas Abertas",
]

# A Black não tem Pré-Qualificação: o lugar dela no funil é ocupado pelo
# Aquecimento — mesma função (esquentar a base antes de abrir o cadastro), nome
# diferente. Também não tem Aulas no Ar nem Replay. Em vez de espalhar
# `if black` pelos leitores e pelo debriefing, tudo pergunta a estas duas
# funções qual é a etapa e qual é a ordem.
ETAPAS_ORDEM_BLACK: list[str] = [
    "Aquecimento",
    "Captação",
    "Lembrete",
    "Matrículas Abertas",
]


def _e_black(launch_code: str | None) -> bool:
    return str(launch_code or "").strip().upper().startswith("BV")


def etapas_ordem(launch_code: str | None = None) -> list[str]:
    """Ordem das etapas do funil para este lançamento."""
    return ETAPAS_ORDEM_BLACK if _e_black(launch_code) else ETAPAS_ORDEM


def etapa_prequali(launch_code: str | None = None) -> str:
    """Nome da etapa que ocupa o papel de Pré-Qualificação neste lançamento."""
    return "Aquecimento" if _e_black(launch_code) else "Pré-Qualificação"


# Apelidos de armazenamento: onde o dado de um lançamento foi gravado quando o
# nome usado NÃO é o código do lançamento. A automação de grupos de WhatsApp
# gravou a Black com o nome da trilha — a tabela de membros é `base_forte` e as
# linhas do Sheets vêm com `launch_code = 'base-forte'`. Como a tabela `BV_26`
# existe mas está VAZIA, sem este apelido a /whatsapp do BV-26 abre toda zerada
# (achado em 07/10/26: 17.136 membros e 10 dias de diário invisíveis).
#
# O conserto definitivo é a automação gravar o código do lançamento; até lá o
# apelido fica aqui, num lugar só, e não espalhado pelos leitores.
APELIDOS_ARMAZENAMENTO: dict[str, tuple[str, ...]] = {
    "BV-26": ("base_forte", "base-forte"),
}


# A /whatsapp mostra dois blocos de grupos. Num lançamento normal são Normais e VIP; na Black são a
# BLACK VITALÍCIA (o bloco principal: grupos "Desconto Black Vitalícia #N" e "Black Vitalícia 2026 #N",
# gravados na tabela `BV_26`) e a BASE FORTE (tabela `base_forte`, já encerrada).
ROTULOS_BLOCOS_WHATSAPP: dict[str, str] = {"normal": "Grupos Normais", "vip": "Grupos VIP"}
ROTULOS_BLOCOS_WHATSAPP_BLACK: dict[str, str] = {"normal": "Black Vitalícia", "vip": "Base Forte"}


def rotulos_blocos_whatsapp(launch_code: str | None = None) -> dict[str, str]:
    return ROTULOS_BLOCOS_WHATSAPP_BLACK if _e_black(launch_code) else ROTULOS_BLOCOS_WHATSAPP


def e_black(launch_code: str | None = None) -> bool:
    return _e_black(launch_code)


def apelidos_armazenamento(launch_code: str | None = None) -> tuple[str, ...]:
    """Outros nomes sob os quais o dado deste lançamento pode estar gravado."""
    return APELIDOS_ARMAZENAMENTO.get(str(launch_code or "").strip().upper(), ())


# Vocabulário de público ("clima"). A Black não tem Quente/Frio/Específico: o
# público dela é Aluno (base do LMS), Super Quente (engajou com a oferta) e Novo.
# Quem fixa a lista normal numa página da Black mostra três linhas zeradas —
# foi o que aconteceu em /pre-qualificacao e /captacao com o BV-26.
CLIMAS_ORDEM: list[str] = ["Quente", "Frio", "Específico"]
CLIMAS_ORDEM_BLACK: list[str] = ["Aluno", "Super Quente", "Novo"]


def climas_ordem(launch_code: str | None = None) -> list[str]:
    """Públicos a exibir, na ordem, para este lançamento."""
    return CLIMAS_ORDEM_BLACK if _e_black(launch_code) else CLIMAS_ORDEM

PRODUCT_BY_PREFIX: dict[str, tuple[str, str, int]] = {
    "PI":       ("INSS",           "Instituto Nacional do Seguro Social", 1),
    "PES":      ("TJ-SP",          "Tribunal de Justiça de São Paulo",    2),
    "PBB":      ("Banco do Brasil", "Banco do Brasil",                    3),
    "PERPETUO": ("PERPETUO",       "Produto Perpétuo",                    4),
    # BV = Black Vitálicia: promoção anual multiproduto (INSS + TJ-SP + BB
    # na mesma campanha), fora do ciclo normal de lançamento por produto.
    "BV":       ("Black Vitalícia", "Black Vitalícia (multiproduto)",     5),
}

LAUNCH_ACCENT: dict[str, str] = {
    "PES-JAN-26": "#764ba2",
    "PBB-FEV-26": "#667eea",
    "PBB-ABR-26": "#f5576c",
    "PES-MAI-26": "#0f766e",
    "PES-MAR-26": "#2f5ee3",
    "PI-ABR-26":  "#e67e22",
    "PI-JAN-26":  "#16a085",
    "PERPETUO":   "#e74c3c",
    "BV-25":      "#111827",
    "BV-26":      "#f97316",
}

LAUNCH_SHORT: dict[str, str] = {
    "PES-JAN-26": "JAN",
    "PBB-FEV-26": "FEV",
    "PBB-ABR-26": "ABR",
    "PES-MAI-26": "MAI",
    "PES-MAR-26": "MAR",
    "PI-ABR-26":  "ABR",
    "PI-JAN-26":  "JAN",
    "PERPETUO":   "PERP",
    "BV-25":      "BLACK",
    "BV-26":      "BLACK",
}

LAUNCH_NAMES: dict[str, str] = {
    "PES-JAN-26": "TJ-SP - Janeiro 2026",
    "PBB-FEV-26": "Banco do Brasil - Fevereiro 2026",
    "PBB-ABR-26": "Banco do Brasil - Abril 2026",
    "PES-MAI-26": "TJ-SP - Maio 2026",
    "PES-MAR-26": "TJ-SP - Março 2026",
    "PI-ABR-26":  "INSS - Abril 2026",
    "PI-JAN-26":  "INSS - Janeiro 2026",
    "PERPETUO":   "Perpétuo - Geral",
    "BV-25":      "Black Vitalícia 2025",
    "BV-26":      "Black Vitalícia 2026",
}

# Campanha de e-mail do AC raramente traz o código do lançamento no nome, então
# ac_campaigns.lancamento_codigo fica NULL em praticamente todas (3.325 de 3.325
# em set/26). O vínculo com o lançamento sai da data de envio + uma palavra do
# produto no nome. Usado pelo leitor (frontend) e pelo ETL de engajamento, que
# precisam enxergar exatamente o mesmo conjunto de campanhas.
AC_KEYWORDS_BY_PREFIX: dict[str, list[str]] = {
    "PBB": ["bb", "banco do brasil"],
    "PES": ["tjsp", "escrevente"],
    "PI":  ["inss"],
}
AC_KEYWORDS_TODAS: list[str] = ["inss", "tjsp", "bb", "banco do brasil"]


def ac_keywords(launch_code: str) -> list[str]:
    """Palavras que identificam o produto no nome da campanha de e-mail."""
    prefixo = (launch_code or "").split("-")[0].upper()
    return AC_KEYWORDS_BY_PREFIX.get(prefixo, AC_KEYWORDS_TODAS)


# Metas de faturamento líquido do ano (R$), somando todos os lançamentos do ano, em degraus
# crescentes (Meta, Super meta, Meta desafio). Vêm de config/anos/<ano>.yaml — preparar um ano
# novo é criar o arquivo dele. Aparecem no Resumo Executivo de /lancamentos. Variável de
# ambiente no serviço do site sobrescreve cada degrau: META_FATURAMENTO_ANUAL_<ano>,
# META_SUPER_ANUAL_<ano>, META_DESAFIO_ANUAL_<ano>.
_METAS_ENV = ("META_FATURAMENTO_ANUAL", "META_SUPER_ANUAL", "META_DESAFIO_ANUAL")
_NOMES_DEGRAU = ("Meta", "Super meta", "Meta desafio")


def _metas_do_arquivo(ano: int) -> list[tuple[str, float]]:
    from pathlib import Path  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    arq = Path(__file__).resolve().parent.parent / "config" / "anos" / f"{ano}.yaml"
    try:
        dados = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
        return [(str(m["nome"]), float(m["valor"])) for m in (dados.get("metas") or [])]
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError):
        return []   # ano sem arquivo (ou arquivo inválido): sem meta, a página só esconde a barra


def _numero_env(bruto: str | None) -> float | None:
    if not bruto:
        return None
    try:
        return float(bruto.replace(".", "").replace(",", ".")) if "," in bruto else float(bruto)
    except ValueError:
        return None


def metas_faturamento_anual(ano: int) -> list[tuple[str, float]]:
    """Degraus de meta do ano (Meta, Super meta, Meta desafio); vazio se o ano não tem meta."""
    import os  # noqa: PLC0415

    base = _metas_do_arquivo(ano)
    for i, var in enumerate(_METAS_ENV):
        v = _numero_env(os.environ.get(f"{var}_{ano}"))
        if v is None:
            continue
        if i < len(base):
            base[i] = (base[i][0], v)
        elif i == len(base):
            base.append((_NOMES_DEGRAU[i], v))
    return base


def meta_faturamento_anual(ano: int) -> float | None:
    """A meta base (primeiro degrau)."""
    metas = metas_faturamento_anual(ano)
    return metas[0][1] if metas else None


# Cores de cada produto (identidade dos concursos), usadas na faixa dos cartões de /lancamentos.
# A chave é o prefixo do código do lançamento (PI-AGO-26 -> "PI"); PERPETUO não é lançamento,
# mas tem paleta própria (criada em 21/10/26: violeta + turquesa, que não colide com os concursos).
# Pantone convertido para o hex mais próximo na tela: 347 C ~ #009A44, 136 C ~ #F2B83A,
# 300 C ~ #005EB8, 538 C ~ #C9D5E6; BB: amarelo RGB 252 252 48 e azul RGB 70 94 255.
PALETA_PRODUTO: dict[str, dict] = {
    "PI": {"nome": "INSS", "destaque": "#009A44", "pesos": [5, 3, 3, 1.4, 1, 1],
           "cores": ["#009A44", "#F2B83A", "#005EB8", "#C9D5E6", "#6B7280", "#111827"]},
    "PES": {"nome": "TJ-SP", "destaque": "#C8102E", "pesos": [1, 2, 2], "cores": ["#FFFFFF", "#C8102E", "#00A859"]},
    "PBB": {"nome": "Banco do Brasil", "destaque": "#465EFF", "pesos": [3, 2], "cores": ["#FCFC30", "#465EFF"]},
    "BV": {"nome": "Black Vitalícia", "destaque": "#C9A227", "pesos": [3, 2], "cores": ["#111827", "#C9A227"]},
    "DISTRIBUICAO": {"nome": "Distribuição", "destaque": "#F59E0B", "pesos": [3, 2, 1], "cores": ["#F59E0B", "#FCD34D", "#111827"]},
    "PERPETUO": {"nome": "Perpétuo", "destaque": "#6C4FD3", "pesos": [3, 2, 1], "cores": ["#6C4FD3", "#14B8A6", "#C4B5FD"]},
}


def paleta_do_produto(prefixo: str | None) -> list[str]:
    return list((PALETA_PRODUTO.get(str(prefixo or "").upper()) or {}).get("cores") or [])

