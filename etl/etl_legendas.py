"""
ETL: legendas dos criativos → Supabase (ad_transcricoes, ad_transcricao_linhas,
ad_copy_atributos)

Lê os .txt de `analises/[LANCAMENTO]/Legendas/`, quebra em blocos de fonte,
parseia a minutagem linha a linha e classifica o que dá pra classificar por
regex. Base da página "Análise de Copys" — plano em
docs/projetos/PLANO_ANALISE_COPYS.md.

    python etl/etl_legendas.py --launch PES-SET-26
    python etl/etl_legendas.py --all
    python etl/etl_legendas.py --launch PES-SET-26 --dry-run   # não toca no banco

Fora do scheduler de propósito: legenda não muda de hora em hora.

ATENÇÃO — material bruto (achado 17/09/26, PES-SET-26):
a maioria dos arquivos é transcrição da filmagem crua, não do corte final
publicado. Em AD269 os 3 blocos abrem todos em [00:00] com falas diferentes
(um por ator/câmera); AD247 tem 299s com takes descartados ("Pera aí, fazer de
novo?") para um anúncio de ~60s. Não dá pra saber mecanicamente qual fala abre
o anúncio. Por isso só `fonte_tipo='corte_final'` recebe `hook_confiavel=True`,
e a decisão de 17/09/26 foi **não** reconstruir a minutagem dos brutos: eles
entram pro texto e pra classificação, mas ficam fora de toda análise temporal.
"""
import argparse
import hashlib
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import bindparam, text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
from db import get_engine
from logger import get_logger

load_dotenv()
logger = get_logger("etl_legendas")

RAIZ = Path(__file__).parent.parent
RX_AD = re.compile(r"^(AD\d+)", re.I)
RX_FONTE = re.compile(r"^---\s*Fonte:\s*(.+?)\s*---\s*$")
RX_LINHA = re.compile(r"^\[(\d+):(\d+)\]\s*(-\s*)?(.*)$")
RX_SEM_FALA = re.compile(r"n[aã]o h[aá] legenda de fala|sem [aá]udio falado", re.I)

# Fonte é o corte final quando o nome do arquivo é o nome do anúncio
# ("AD296 - Ivan Carro + leg PES-MAI-26 (Story).mp4") e não um arquivo de
# câmera ("C0068.MP4", "IMG_8559 2.MOV").
RX_FONTE_FINAL = re.compile(r"^AD\d+\s*-", re.I)


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────
def _normalizar(txt: str) -> str:
    """Forma canônica pro hash de roteiro: sem acento, sem pontuação, minúsculo.

    É o que faz AD269 e AD292 caírem no mesmo grupo mesmo tendo sido
    transcritos em momentos diferentes."""
    txt = unicodedata.normalize("NFKD", txt.lower())
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", re.sub(r"\s+", " ", txt)).strip()


def _caminho_relativo(caminho: Path) -> str:
    """Caminho do .txt relativo à raiz do projeto, para gravar em arquivo_origem."""
    try:
        return str(caminho.resolve().relative_to(RAIZ)).replace("\\", "/")
    except ValueError:
        return caminho.name


def parse_arquivo(caminho: Path, lancamento: str) -> list[dict]:
    """Um .txt → lista de blocos, cada um com suas linhas de minutagem."""
    m = RX_AD.match(caminho.name)
    if not m:
        logger.warning("Arquivo sem código ADxxx no nome, ignorado: %s", caminho.name)
        return []
    ad_code = m.group(1).upper()
    bruto = caminho.read_text(encoding="utf-8", errors="replace")

    blocos: list[dict] = []
    atual: dict | None = None
    for linha in bruto.splitlines():
        mf = RX_FONTE.match(linha)
        if mf:
            atual = {"fonte": mf.group(1), "linhas": []}
            blocos.append(atual)
            continue
        ml = RX_LINHA.match(linha)
        if not ml:
            continue
        if atual is None:
            # Arquivo sem cabeçalho "--- Fonte: ---": bloco único implícito.
            atual = {"fonte": "__unico__", "linhas": []}
            blocos.append(atual)
        texto = ml.group(4).strip()
        if not texto:
            continue
        atual["linhas"].append({
            "t_ini_seg": int(ml.group(1)) * 60 + int(ml.group(2)),
            "dialogo": bool(ml.group(3)),   # o "- " marca fala de personagem
            "texto": texto,
        })

    if not blocos:
        # Sem nenhuma linha com timestamp: ou é o placeholder de estático, ou
        # é um arquivo que não conseguimos ler. Os dois viram 'sem_fala', mas
        # o segundo caso merece aviso.
        if not RX_SEM_FALA.search(bruto):
            logger.warning("%s: sem timestamps e sem o aviso de estático — conferir", caminho.name)
        return [{
            "ad_code": ad_code, "ad_name": caminho.stem, "lancamento_codigo": lancamento,
            "fonte": "__sem_fala__", "fonte_ordem": 0, "fonte_tipo": "sem_fala",
            "is_canonica": True, "hook_confiavel": False,
            "duracao_seg": 0, "n_linhas": 0, "n_palavras": 0,
            "texto_completo": "", "roteiro_hash": None,
            "arquivo_origem": _caminho_relativo(caminho),
            "linhas": [],
        }]

    saida = []
    for ordem, bloco in enumerate(blocos):
        linhas = bloco["linhas"]
        if not linhas:
            continue
        duracao = linhas[-1]["t_ini_seg"]
        texto_completo = "\n".join(ln["texto"] for ln in linhas)
        # Alterna A/B a cada fala só quando o arquivo marca diálogo com "- ".
        # Sem essa marca não dá pra inferir quem fala — fica NULL.
        falante = "A"
        for i, ln in enumerate(linhas):
            ln["ordem"] = i
            ln["t_fim_seg"] = linhas[i + 1]["t_ini_seg"] if i + 1 < len(linhas) else None
            ln["n_palavras"] = len(ln["texto"].split())
            # quartil: em qual quarto do vídeo a fala cai (ponte com views_25/50/75/100)
            ln["quartil"] = (
                min(4, int(ln["t_ini_seg"] / duracao * 4) + 1) if duracao > 0 else 1
            )
            if ln["dialogo"]:
                ln["falante"] = falante
                falante = "B" if falante == "A" else "A"
            else:
                ln["falante"] = None

        fonte_tipo = "corte_final" if RX_FONTE_FINAL.match(bloco["fonte"]) else "bruto"
        saida.append({
            "ad_code": ad_code, "ad_name": caminho.stem, "lancamento_codigo": lancamento,
            "fonte": bloco["fonte"], "fonte_ordem": ordem, "fonte_tipo": fonte_tipo,
            "is_canonica": False,   # decidido em escolher_canonica()
            "hook_confiavel": False,
            "duracao_seg": duracao,
            "n_linhas": len(linhas),
            "n_palavras": sum(ln["n_palavras"] for ln in linhas),
            "texto_completo": texto_completo,
            "roteiro_hash": hashlib.sha1(
                _normalizar(texto_completo).encode("utf-8")
            ).hexdigest(),
            "arquivo_origem": _caminho_relativo(caminho),
            "linhas": linhas,
        })
    return saida


def escolher_canonica(blocos: list[dict]) -> None:
    """Marca, entre os blocos de um mesmo ADxxx, qual representa o anúncio.

    Corte final ganha sempre — é o único caso em que a minutagem é a do vídeo
    publicado, e só ele recebe hook_confiavel. Entre brutos, o mais longo (mais
    completo), mas sem confiabilidade de gancho: a decisão de 17/09/26 foi não
    reconstruir a timeline desses."""
    if not blocos:
        return
    finais = [b for b in blocos if b["fonte_tipo"] == "corte_final"]
    if finais:
        escolhido = max(finais, key=lambda b: (b["n_linhas"], -b["fonte_ordem"]))
        escolhido["is_canonica"] = True
        escolhido["hook_confiavel"] = True
        return
    escolhido = max(blocos, key=lambda b: (b["n_linhas"], -b["fonte_ordem"]))
    escolhido["is_canonica"] = True
    escolhido["hook_confiavel"] = False


# ─────────────────────────────────────────────────────────────────────────────
# Classificação automática (origem='auto')
# ─────────────────────────────────────────────────────────────────────────────
# Só o que regex acerta com confiança. O resto (gancho_tipo temático, promessa,
# cenário) fica pra LLM/humano — ver seção 4.4 do PLANO_ANALISE_COPYS.
REGRAS_AUTO: list[tuple[str, str, re.Pattern]] = [
    ("prova",    "720_vagas",       re.compile(r"\b720\b")),
    ("prova",    "93_acerto",       re.compile(r"\b93\s*%|\b93\s*por cento")),
    ("prova",    "salario",         re.compile(r"R\$\s?[\d.,]+|sal[aá]rio inicial")),
    ("prova",    "contrato_banca",  re.compile(r"contrato assinado|banca (j[aá] )?(foi )?escolhida|banco organizador", re.I)),
    ("promessa", "gratuidade",      re.compile(r"\bgratuit[oa]|\bgr[aá]tis\b|100%\s*gratuito", re.I)),
    ("promessa", "plano_de_estudo", re.compile(r"plano de estudo", re.I)),
    ("promessa", "aprovacao",       re.compile(r"\baprovad[oa]\b|ser aprovado", re.I)),
    ("cta_tipo", "saiba_mais",      re.compile(r"saiba mais", re.I)),
    ("cta_tipo", "botao_abaixo",    re.compile(r"bot[aã]o (que est[aá] )?(aqui )?embaixo|toca no bot[aã]o", re.I)),
    ("cta_tipo", "grupo_whatsapp",  re.compile(r"grupo de whatsapp|comunidade do whatsapp", re.I)),
    ("cta_tipo", "cadastro",        re.compile(r"fazer o (seu )?cadastro|se cadastrar", re.I)),
    ("objecao",  "preco",           re.compile(r"sem grana|n[aã]o (vou )?ter dinheiro|caro", re.I)),
    ("objecao",  "iniciante",       re.compile(r"\biniciante\b|do zero|nunca estudei", re.I)),
    ("objecao",  "nivel_medio",     re.compile(r"ensino m[eé]dio|n[ií]vel m[eé]dio", re.I)),
    ("objecao",  "idade",           re.compile(r"mais de \d{2} anos|\+\s?40\b", re.I)),
    ("objecao",  "tempo",           re.compile(r"d[aá] tempo|quantas horas por dia", re.I)),
]


def classificar(bloco: dict) -> list[dict]:
    """Atributos que saem por regex do texto canônico."""
    if not bloco["texto_completo"]:
        return [{"dimensao": "formato", "valor": "imagem_estatica", "origem": "auto"}]

    achados = [
        {"dimensao": dim, "valor": val, "origem": "auto"}
        for dim, val, rx in REGRAS_AUTO
        if rx.search(bloco["texto_completo"])
    ]

    # Formato pelo nº de falantes marcados com "- " no arquivo.
    falantes = {ln.get("falante") for ln in bloco["linhas"] if ln.get("falante")}
    if len(falantes) > 1:
        achados.append({"dimensao": "formato", "valor": "dialogo_2p", "origem": "auto"})

    # Gancho só sai quando a minutagem é a do vídeo publicado — em material
    # bruto os 3 primeiros segundos não são os do anúncio.
    if bloco["hook_confiavel"]:
        gancho = " ".join(ln["texto"] for ln in bloco["linhas"] if ln["t_ini_seg"] < 3)
        if gancho:
            if "?" in gancho:
                achados.append({"dimensao": "gancho_tipo", "valor": "pergunta", "origem": "auto"})
            if re.search(r"\d", gancho):
                achados.append({"dimensao": "gancho_tipo", "valor": "numero", "origem": "auto"})

    vistos, unicos = set(), []
    for a in achados:
        chave = (a["dimensao"], a["valor"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(a)
    return unicos


# ─────────────────────────────────────────────────────────────────────────────
# Persistência
# ─────────────────────────────────────────────────────────────────────────────
def gravar(blocos: list[dict]) -> None:
    agora = datetime.now(timezone.utc)
    engine = get_engine()

    sql_transc = text("""
        INSERT INTO ad_transcricoes (lancamento_codigo, ad_code, ad_name, fonte, fonte_ordem,
                                     fonte_tipo, is_canonica, hook_confiavel, duracao_seg,
                                     n_linhas, n_palavras, texto_completo, roteiro_hash,
                                     arquivo_origem, updated_at)
        VALUES (:lancamento_codigo, :ad_code, :ad_name, :fonte, :fonte_ordem,
                :fonte_tipo, :is_canonica, :hook_confiavel, :duracao_seg,
                :n_linhas, :n_palavras, :texto_completo, :roteiro_hash,
                :arquivo_origem, :updated_at)
        ON CONFLICT (lancamento_codigo, ad_code, fonte) DO UPDATE SET
            ad_name = EXCLUDED.ad_name, fonte_ordem = EXCLUDED.fonte_ordem,
            fonte_tipo = EXCLUDED.fonte_tipo, is_canonica = EXCLUDED.is_canonica,
            hook_confiavel = EXCLUDED.hook_confiavel, duracao_seg = EXCLUDED.duracao_seg,
            n_linhas = EXCLUDED.n_linhas, n_palavras = EXCLUDED.n_palavras,
            texto_completo = EXCLUDED.texto_completo, roteiro_hash = EXCLUDED.roteiro_hash,
            arquivo_origem = EXCLUDED.arquivo_origem, updated_at = EXCLUDED.updated_at
        RETURNING id
    """)
    sql_linha = text("""
        INSERT INTO ad_transcricao_linhas (transcricao_id, ordem, t_ini_seg, t_fim_seg,
                                           quartil, falante, texto, n_palavras)
        VALUES (:transcricao_id, :ordem, :t_ini_seg, :t_fim_seg,
                :quartil, :falante, :texto, :n_palavras)
        ON CONFLICT (transcricao_id, ordem) DO UPDATE SET
            t_ini_seg = EXCLUDED.t_ini_seg, t_fim_seg = EXCLUDED.t_fim_seg,
            quartil = EXCLUDED.quartil, falante = EXCLUDED.falante,
            texto = EXCLUDED.texto, n_palavras = EXCLUDED.n_palavras
    """)
    # A curadoria humana é a verdade: uma linha marcada como 'humano' nunca é
    # rebaixada pro que o regex acha.
    sql_attr = text("""
        INSERT INTO ad_copy_atributos (lancamento_codigo, ad_code, dimensao, valor,
                                       origem, confianca, updated_at)
        VALUES (:lancamento_codigo, :ad_code, :dimensao, :valor, :origem, NULL, :updated_at)
        ON CONFLICT (lancamento_codigo, ad_code, dimensao, valor) DO UPDATE SET
            updated_at = EXCLUDED.updated_at
        WHERE ad_copy_atributos.origem <> 'humano'
    """)

    sql_limpar_auto = text(
        "DELETE FROM ad_copy_atributos"
        " WHERE lancamento_codigo = :c AND ad_code = :ad"
        "   AND origem = 'auto' AND valor NOT IN :mantidos"
    ).bindparams(bindparam("mantidos", expanding=True))

    with engine.begin() as conn:
        for bloco in blocos:
            campos = {k: v for k, v in bloco.items() if k != "linhas"}
            campos["updated_at"] = agora
            transc_id = conn.execute(sql_transc, campos).scalar_one()

            # Re-ingestão de um arquivo reeditado pode encurtar o bloco; sem
            # isso as linhas antigas do fim sobreviveriam ao UPSERT.
            conn.execute(
                text("DELETE FROM ad_transcricao_linhas"
                     " WHERE transcricao_id = :id AND ordem >= :n"),
                {"id": transc_id, "n": len(bloco["linhas"])},
            )
            for ln in bloco["linhas"]:
                conn.execute(sql_linha, {
                    "transcricao_id": transc_id, "ordem": ln["ordem"],
                    "t_ini_seg": ln["t_ini_seg"], "t_fim_seg": ln["t_fim_seg"],
                    "quartil": ln["quartil"], "falante": ln["falante"],
                    "texto": ln["texto"], "n_palavras": ln["n_palavras"],
                })

            if bloco["is_canonica"]:
                atributos = classificar(bloco)
                # Legenda reeditada pode deixar de casar com uma regra: sem
                # limpar, a tag antiga sobrevive e entra no pivô como se ainda
                # valesse. Só mexe no que o ETL escreveu — 'humano' e 'llm'
                # ficam intactos.
                valores = [a["valor"] for a in atributos] or [""]
                conn.execute(sql_limpar_auto, {
                    "c": bloco["lancamento_codigo"], "ad": bloco["ad_code"],
                    "mantidos": valores,
                })
                for attr in atributos:
                    conn.execute(sql_attr, {
                        "lancamento_codigo": bloco["lancamento_codigo"],
                        "ad_code": bloco["ad_code"], **attr, "updated_at": agora,
                    })


# ─────────────────────────────────────────────────────────────────────────────
# Relatório de validação
# ─────────────────────────────────────────────────────────────────────────────
def validar(lancamento: str, blocos: list[dict], piso_gasto: float = 100.0) -> None:
    """Confronta os ADxxx com legenda contra os que de fato veicularam.

    O furo que mais dói é o segundo: criativo que gastou de verdade e não tem
    legenda nenhuma — some silenciosamente de qualquer análise de copy."""
    com_legenda = {b["ad_code"] for b in blocos}
    engine = get_engine()
    with engine.connect() as conn:
        gasto = dict(conn.execute(text(r"""
            SELECT ad_code, SUM(gasto) FROM (
                SELECT upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')) AS ad_code,
                       spend AS gasto
                FROM meta_ads_daily WHERE lancamento_codigo = :c
                UNION ALL
                SELECT upper(regexp_replace(ad_name, '^(AD\d+).*', '\1')),
                       cost
                FROM google_ads_daily WHERE lancamento_codigo = :c
            ) u WHERE ad_code ~ '^AD[0-9]+$' GROUP BY ad_code
        """), {"c": lancamento}).fetchall())

    veiculados = set(gasto)
    sem_veiculacao = sorted(com_legenda - veiculados)
    sem_legenda = sorted(
        (ad for ad in veiculados - com_legenda if float(gasto[ad] or 0) >= piso_gasto),
        key=lambda ad: -float(gasto[ad] or 0),
    )

    print(f"\n{'=' * 70}\nVALIDAÇÃO — {lancamento}\n{'=' * 70}")
    print(f"ADxxx com legenda: {len(com_legenda)} · que veicularam: {len(veiculados)}")

    if sem_veiculacao:
        print(f"\n⚠️  Legenda sem veiculação neste lançamento ({len(sem_veiculacao)}):")
        print("   " + ", ".join(sem_veiculacao))
    if sem_legenda:
        print(f"\n❌ Gastaram ≥ R$ {piso_gasto:.0f} e NÃO têm legenda ({len(sem_legenda)}):")
        for ad in sem_legenda[:20]:
            print(f"   {ad}: R$ {float(gasto[ad]):,.2f}")
        if len(sem_legenda) > 20:
            print(f"   ... e mais {len(sem_legenda) - 20}")
    if not sem_veiculacao and not sem_legenda:
        print("\n✅ Cobertura completa: toda legenda veiculou e todo gasto tem legenda.")


def relatorio_parse(lancamento: str, blocos: list[dict]) -> None:
    """O que o parser entendeu — roda com ou sem banco."""
    canonicas = [b for b in blocos if b["is_canonica"]]
    por_tipo: dict[str, int] = {}
    for b in canonicas:
        por_tipo[b["fonte_tipo"]] = por_tipo.get(b["fonte_tipo"], 0) + 1

    print(f"\n{'=' * 70}\nPARSE — {lancamento}\n{'=' * 70}")
    print(f"{len(canonicas)} anúncios · {len(blocos)} blocos · "
          f"{sum(b['n_linhas'] for b in blocos)} linhas com timestamp")
    print("Tipo da fonte canônica: " + " · ".join(f"{k}={v}" for k, v in sorted(por_tipo.items())))
    print(f"Com gancho confiável (minutagem do vídeo publicado): "
          f"{sum(1 for b in canonicas if b['hook_confiavel'])}")

    grupos: dict[str, list[str]] = {}
    for b in blocos:
        if b["roteiro_hash"]:
            grupos.setdefault(b["roteiro_hash"], []).append(b["ad_code"])
    repetidos = sorted(
        {tuple(sorted(set(ads))) for ads in grupos.values() if len(set(ads)) > 1}
    )
    if repetidos:
        print(f"\nRoteiros compartilhados entre ADxxx ({len(repetidos)} grupos) — "
              "agrupar no ranking, senão o gancho aparece fatiado:")
        for g in repetidos:
            print("   " + " = ".join(g))


# ─────────────────────────────────────────────────────────────────────────────
def pastas_de_legenda(launch: str | None) -> list[tuple[str, Path]]:
    achadas = []
    for pasta in sorted((RAIZ / "analises").glob("[[]*[]]/Legendas")):
        codigo = pasta.parent.name.strip("[]")
        if launch is None or codigo.upper() == launch.upper():
            achadas.append((codigo, pasta))
    return achadas


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingere legendas de criativos (ADxxx) no Supabase")
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--launch", help="código do lançamento, ex: PES-SET-26")
    grupo.add_argument("--all", action="store_true", help="varre analises/*/Legendas/")
    ap.add_argument("--dry-run", action="store_true", help="só parseia e relata, não grava")
    ap.add_argument("--piso-gasto", type=float, default=100.0,
                    help="gasto mínimo pra cobrar legenda de um ADxxx (padrão: 100)")
    args = ap.parse_args()

    pastas = pastas_de_legenda(None if args.all else args.launch)
    if not pastas:
        alvo = "analises/*/Legendas/" if args.all else f"analises/[{args.launch}]/Legendas/"
        logger.error("Nenhuma pasta de legendas encontrada em %s", alvo)
        return 1

    for lancamento, pasta in pastas:
        blocos: list[dict] = []
        for arquivo in sorted(pasta.glob("*.txt")):
            do_arquivo = parse_arquivo(arquivo, lancamento)
            escolher_canonica(do_arquivo)
            blocos.extend(do_arquivo)

        if not blocos:
            logger.warning("%s: nenhuma legenda parseada em %s", lancamento, pasta)
            continue

        relatorio_parse(lancamento, blocos)

        if args.dry_run:
            logger.info("%s: dry-run, nada gravado", lancamento)
            continue

        gravar(blocos)
        logger.info("%s: %d blocos gravados", lancamento, len(blocos))
        validar(lancamento, blocos, args.piso_gasto)

    return 0


if __name__ == "__main__":
    sys.exit(main())
