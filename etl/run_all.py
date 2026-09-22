"""
Orquestrador ETL — roda todos os scripts em sequência.

Uso:
    python etl/run_all.py --since 2026-04-01 --until 2026-04-30

    # Roda apenas um ETL específico:
    python etl/run_all.py --since 2026-04-01 --until 2026-04-30 --only meta_ads

    # Cargas via CSV (para fontes sem API configurada ainda):
    python etl/run_all.py --csv-mode --campaign-folder "analises/[PBB-ABR-26]" --period 2026-04
"""
import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from logger import get_logger
from etl_runs import start_run, finish_run

BASE = Path(__file__).parent
load_dotenv(dotenv_path=BASE.parent / ".env")
logger = get_logger("etl.run_all")


# Sem timeout aqui, um hang de rede dentro de QUALQUER script (visto em
# etl_active_campaign.py, mas vale pra qualquer fonte) trava o subprocess.run
# pra sempre — e como run_api_mode roda as fontes em sequência, tudo que vem
# depois (meta_ads, google_ads, ...) nunca chega a rodar. Foi o que aconteceu
# em 01/09: active_campaign travou às 8h32 e nada mais rodou por ~6h, até
# alguém notar e reiniciar o container na mão. Com timeout, o processo
# travado é morto e o orquestrador segue pra próxima fonte sozinho.
_TIMEOUT_PADRAO_SEGUNDOS = 900  # 15 min — folgado pra janela normal de 3 dias

# active_campaign pagina 100 contatos por vez sobre TODOS os "atualizados" na
# janela (updated_after/updated_before, não só criados) — um pico de atividade
# na conta (bulk de tag/campo/automação) pode inflar isso pra dezenas de
# milhares de contatos, bem acima do que 15 min aguenta paginar (visto em
# 11/09/26: 900s deixou de bastar quando o "atualizados" no dia saltou de
# ~1-10 mil/dia pra ~65 mil num único dia). 30 min dá folga sem deixar o
# processo travar pra sempre se a API realmente cair.
_TIMEOUTS_POR_FONTE = {"active_campaign": 1800}

# Um traceback de erro HTTP carrega a URL COMPLETA da chamada que falhou — e
# no Meta/Google o segredo vai na query string. Sem isso, o token vaza em
# texto puro pra etl_runs.error_message e pro ERROR_WEBHOOK_URL (visto em
# 15/09/26: um 500 do Graph gravou o META_ACCESS_TOKEN inteiro na tabela).
_SEGREDOS_EM_URL_RE = re.compile(
    r"\b((?:access_token|refresh_token|client_secret|developer_token|api_key|apikey|key|token)=)[^&\s\"']+",
    re.IGNORECASE,
)


def redigir_segredos(texto: str) -> str:
    """Troca o valor de qualquer parâmetro sensível por <REDACTED>."""
    if not texto:
        return texto
    return _SEGREDOS_EM_URL_RE.sub(r"\1<REDACTED>", texto)


def run(cmd: list[str], label: str, source: str | None = None, timeout: int = _TIMEOUT_PADRAO_SEGUNDOS) -> int:
    logger.info("Iniciando: %s", label)
    run_id = start_run(source) if source else None
    try:
        # capture_output pra guardar o stderr real em etl_runs.error_message —
        # sem isso, uma falha só vira "exit code 1" sem detalhe nenhum (foi o
        # caso do google_ads falhando silenciosamente em 03/09, sem dar pra
        # saber o motivo depois). Ainda ecoa tudo pro stdout/stderr do processo
        # pai, então o scheduler continua capturando a saída completa também.
        result = subprocess.run(cmd, timeout=timeout, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        returncode = result.returncode
        if result.stdout:
            sys.stdout.write(redigir_segredos(result.stdout))
        if result.stderr:
            sys.stderr.write(redigir_segredos(result.stderr))
    except subprocess.TimeoutExpired:
        logger.error("Timeout em '%s' após %ds — processo travado, seguindo para a próxima fonte.", label, timeout)
        finish_run(run_id, status="error", error=f"timeout apos {timeout}s")
        return -1
    if returncode != 0:
        logger.error("Falha em '%s' (código %d)", label, returncode)
        detalhe = redigir_segredos((result.stderr or result.stdout or "").strip()[-3000:])
        finish_run(run_id, status="error", error=f"exit code {returncode}: {detalhe}" if detalhe else f"exit code {returncode}")
    else:
        logger.info("Concluído: %s", label)
        finish_run(run_id, status="ok")
    return returncode


def run_api_mode(since: str, until: str, only: str | None):
    scripts = {
        "active_campaign": [sys.executable, str(BASE / "etl_active_campaign.py"),
                            "--api", "--since", since, "--until", until],
        "meta_ads":        [sys.executable, str(BASE / "etl_meta_ads.py"),
                            "--since", since, "--until", until],
        "google_ads":      [sys.executable, str(BASE / "etl_google_ads.py"),
                            "--since", since, "--until", until],
        # Typeform removido do pipeline automático: conta cancelada, dados
        # agora vêm do backup em Supabase (frontend/db_readers/typeform.py).
        # etl_typeform.py continua existindo pra rodar manualmente se o
        # token ainda for válido.
        # Estatísticas de campanhas de e-mail do AC (envios/aberturas/cliques).
        # A API devolve o histórico completo — não usa --since/--until.
        "ac_campaigns":    [sys.executable, str(BASE / "etl_ac_campaigns.py"), "--api"],
        # Cliques no PDF do ebook (e-mail da automação do lançamento), contato
        # a contato — alimenta "Ebook → compra" no debriefing. Só lançamentos
        # ativos/recentes; não usa --since/--until.
        "ac_ebook":        [sys.executable, str(BASE / "etl_ac_ebook.py"), "--api"],
        # Quem abriu e quem clicou cada campanha de e-mail, contato a contato —
        # é o que permite cruzar e-mail com venda em /crm-campanhas. Só
        # lançamentos ativos/recentes; não usa --since/--until.
        "ac_engajamento":  [sys.executable, str(BASE / "etl_ac_engajamento.py"), "--api"],
        "whatsapp":        [sys.executable, str(BASE / "etl_whatsapp.py"),
                            "--since", since, "--until", until],
        # Perfil + posts nao usam --since/--until (sempre pega o snapshot atual).
        "instagram":       [sys.executable, str(BASE / "etl_instagram.py")],
        # Só leitura do Sheets do sendflow-analytics-poller (Total/Total
        # Limpo/Grupos Cheios/Entradas/Saídas) — leve, sem --since/--until.
        "sheets_contagem": [sys.executable, str(BASE / "etl_sheets_contagem.py")],
        "ga4":             [sys.executable, str(BASE / "etl_ga4.py"),
                            "--since", since, "--until", until],
        # DESATIVADO 01/09/26: a mv_atribuicao_publicos depende das cópias de
        # hotmart/tmb do banco analytics, que estão desatualizadas (43 vendas
        # vs 2502 reais no PI-AGO-26). Reativar só depois de existir sync de
        # vendas pro banco analytics. Atribuição por público no frontend usa
        # read_vendas (banco operacional), que é a fonte correta.
        # "refresh_views": [sys.executable, str(BASE / "refresh_views.py")],
    }

    if only:
        # Aceita lista separada por vírgula: o scheduler divide as fontes em
        # cadências diferentes (rápidas a cada 30 min, lentas de hora em hora)
        # e chama com `--only meta_ads,google_ads,ga4,sheets_contagem`.
        pedidos = [n.strip() for n in only.split(",") if n.strip()]
        desconhecidos = [n for n in pedidos if n not in scripts]
        if desconhecidos:
            raise SystemExit(f"--only: fonte desconhecida {desconhecidos} (válidas: {sorted(scripts)})")
        # Preserva a ordem definida em `scripts`, não a ordem digitada.
        targets = {k: v for k, v in scripts.items() if k in pedidos}
    else:
        targets = scripts
    errors = []
    for name, cmd in targets.items():
        timeout = _TIMEOUTS_POR_FONTE.get(name, _TIMEOUT_PADRAO_SEGUNDOS)
        code = run(cmd, name, source=name, timeout=timeout)
        if code != 0:
            errors.append(name)
    return errors


def run_csv_mode(campaign_folder: str, period: str):
    """
    Modo CSV: importa os exports manuais de uma pasta de campanha específica.
    Detecta automaticamente os CSVs pela estrutura de pastas padrão do projeto.
    """
    folder = Path(campaign_folder)
    errors = []

    # Active Campaign — CSV mais recente
    ac_dir  = folder / "Active Campaign"
    ac_csvs = sorted(ac_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if ac_csvs:
        code = run(
            [sys.executable, str(BASE / "etl_active_campaign.py"), "--from-csv", str(ac_csvs[0])],
            f"active_campaign  <- {ac_csvs[0].name}",
        )
        if code != 0:
            errors.append("active_campaign")
    else:
        logger.warning("[SKIP] Nenhum CSV encontrado em %s", ac_dir)

    # Meta Ads
    meta_dir  = folder / "Meta Ads"
    meta_csvs = sorted(meta_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if meta_csvs:
        code = run(
            [sys.executable, str(BASE / "etl_meta_ads.py"),
             "--from-csv", str(meta_csvs[0])],
            f"meta_ads  <- {meta_csvs[0].name}",
        )
        if code != 0:
            errors.append("meta_ads")
    else:
        logger.warning("[SKIP] Nenhum CSV encontrado em %s", meta_dir)

    # Google Ads — usa o CSV de performance de anúncios
    ga_dir  = folder / "Google Ads"
    ga_csvs = sorted(ga_dir.glob("*anuncios*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not ga_csvs:
        ga_csvs = sorted(ga_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if ga_csvs:
        code = run(
            [sys.executable, str(BASE / "etl_google_ads.py"),
             "--from-csv", str(ga_csvs[0]), "--period", period],
            f"google_ads  <- {ga_csvs[0].name}",
        )
        if code != 0:
            errors.append("google_ads")
    else:
        logger.warning("[SKIP] Nenhum CSV encontrado em %s", ga_dir)

    return errors


def main():
    parser = argparse.ArgumentParser(description="Orquestrador ETL → Supabase")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--since",           metavar="YYYY-MM-DD", help="Data inicial (modo API)")
    mode.add_argument("--csv-mode",        action="store_true",  help="Importa via CSVs exportados manualmente")

    parser.add_argument("--until",          metavar="YYYY-MM-DD", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--only",           metavar="SCRIPT",    help="Roda somente estas fontes (separadas por vírgula): active_campaign | meta_ads | google_ads | ac_campaigns | ac_ebook | ac_engajamento | whatsapp | instagram | sheets_contagem | ga4")
    parser.add_argument("--campaign-folder", metavar="PATH",      help="Pasta da campanha (modo --csv-mode), ex: analises/[PBB-ABR-26]")
    parser.add_argument("--period",          metavar="YYYY-MM",   help="Período da campanha (modo --csv-mode), ex: 2026-04")
    args = parser.parse_args()

    if args.csv_mode:
        if not args.campaign_folder or not args.period:
            parser.error("--csv-mode requer --campaign-folder e --period")
        errors = run_csv_mode(args.campaign_folder, args.period)
    else:
        errors = run_api_mode(args.since, args.until, args.only)

    if errors:
        logger.error("ETL concluído com erros em: %s", ", ".join(errors))
        sys.exit(1)
    else:
        logger.info("Todos os ETLs concluídos com sucesso.")


if __name__ == "__main__":
    main()
