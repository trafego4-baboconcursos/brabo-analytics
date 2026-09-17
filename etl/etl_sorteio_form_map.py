"""
etl/etl_sorteio_form_map.py — Mapeia cada formulário do sorteio (form_id) ao
lançamento a que pertence, gravando em sorteio_form_lancamento.

Por que existe: os formulários não têm o código do lançamento no nome —
"Sorteio - Projeto INSS - Aula 1" se repete idêntico a cada lançamento desde
2023 (74 formulários achados em 15/09/26, ver etl_sorteio_forms.py). Hoje
frontend/db_readers/sorteio.py atribui cada RESPOSTA a um lançamento batendo
`created_at` contra a janela "Aulas no Ar" de cada launch_config — funciona
bem (validado: 10 dos 13 formulários de lançamentos rastreados caem >99% num
lançamento só) mas depende de `aulas_start_date`/`carrinho_start_date`
estarem preenchidos na config; sem eles, a seção "Sorteio" do debriefing
simplesmente não aparece.

Esta tabela é o registro explícito e auditável de "este formulário é deste
lançamento" — serve pra quem opera o sorteio conferir rapidamente qual link é
de qual lançamento, e é uma fonte mais confiável que a data crua pra atribuir
resposta a lançamento (ver por quê abaixo).

Critério de inclusão: maioria simples (>50%) das respostas do formulário
concentrada numa única janela de lançamento rastreado (dim_lancamentos +
launch_config). Analisado em 16/09/26: as 3 "Aula 1" de PI-JAN/ABR/AGO-26
tinham 82-87% num lançamento e o resto inteiro no lançamento ANTERIOR (nunca
no seguinte) — não é form reaproveitado/link velho, é a Aula 1 de verdade
acontecendo ANTES da nossa data de corte: `aulas_start_date` quase nunca é
preenchido em launch_config, então a janela cai pra `carrinho_start_date`,
que é semanas DEPOIS do início real das aulas — a sobra vaza pro fim da
janela do lançamento anterior. O form_id não tem esse problema (um form novo
por lançamento), por isso maioria >50% já é um sinal melhor que a data crua.
Só formulário "fora" (nenhum lançamento rastreado cobre nenhuma resposta
dele) fica de fora — esse sim é histórico anterior ao rastreamento.

Uso:
    python etl/etl_sorteio_form_map.py
"""
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
from db import get_engine
from logger import get_logger

load_dotenv()
logger = get_logger("etl.sorteio_form_map")

DDL = """
CREATE TABLE IF NOT EXISTS sorteio_form_lancamento (
    form_id            TEXT PRIMARY KEY,
    projeto            TEXT NOT NULL,
    lancamento_codigo  TEXT NOT NULL,
    aula               TEXT NOT NULL,
    respostas_totais   INT NOT NULL,
    respostas_no_lanc  INT NOT NULL,
    pct_concentracao   NUMERIC(5,2) NOT NULL,
    atualizado_em      TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_LIMIAR_OK = 50.0  # maioria simples — form_id é sinal melhor que a data de corte (ver docstring)

# Correções manuais de aula por form_id — confirmadas com quem roda o sorteio
# (Luís Felipe, Discord 17/09/26): no PI-AGO-26 o formulário de Aula 2 quebrou
# no dia e o time reciclou o link do formulário de Aula 3 pra receber as
# inscrições de Aula 2 também — por isso esse form_id aparece com aula="Aula 3"
# em sorteio_respostas (nome real no Drive nunca foi corrigido), mas as 3.773
# respostas dele são de Aula 2. Sobrescreve só aqui, não na tabela bruta —
# sorteio_respostas continua refletindo o nome real do formulário no Drive.
_CORRECOES_AULA: dict[str, str] = {
    "1D0-QyQJGbMJPYEeWtEcppyqgp_Nm_aJzXE3qRbDKQUQ": "Aula 2",
}


def _janelas_por_produto(engine, projeto: str) -> dict[str, tuple[str, str]]:
    """{lancamento_codigo: (inicio, fim)} de todos os lançamentos do produto,
    mesma lógica de frontend/db_readers/sorteio.py::_resolve_janela — INICIO
    das Aulas no Ar (ou carrinho, ou data_inicio) até o início das do
    PRÓXIMO, ou hoje se for o mais recente."""
    from datetime import date, timedelta
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from frontend.db_readers.sorteio import _janela_inicio  # noqa: PLC0415

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT codigo, data_inicio FROM dim_lancamentos WHERE projeto = :projeto ORDER BY data_inicio"
        ), {"projeto": projeto}).fetchall()

    codes = [r[0] for r in rows]
    janelas: dict[str, tuple[str, str]] = {}
    for i, (code, data_inicio) in enumerate(rows):
        inicio = _janela_inicio(code, data_inicio)
        if not inicio:
            continue
        if i + 1 < len(rows):
            fim = _janela_inicio(codes[i + 1], rows[i + 1][1])
        else:
            fim = None
        if not fim:
            fim = (date.today() + timedelta(days=1)).isoformat()
        janelas[code] = (inicio, fim)
    return janelas


def build_map(projeto: str) -> list[dict]:
    engine = get_engine()
    janelas = _janelas_por_produto(engine, projeto)

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT form_id, aula, created_at FROM sorteio_respostas WHERE projeto = :projeto"
        ), {"projeto": projeto}).fetchall()

    contagem: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    aula_do_form: dict[str, str] = {}
    for form_id, aula, created_at in rows:
        aula_do_form[form_id] = _CORRECOES_AULA.get(form_id, aula)
        ca = str(created_at)[:10]
        bucket = None
        for code, (inicio, fim) in janelas.items():
            if inicio <= ca < fim:
                bucket = code
                break
        contagem[form_id][bucket] += 1  # bucket=None agrupa "fora de qualquer janela"

    mapeados = []
    for form_id, dist in contagem.items():
        total = sum(dist.values())
        melhor_code, melhor_n = max(dist.items(), key=lambda kv: kv[1])
        if melhor_code is None:
            continue
        pct = melhor_n / total * 100
        if pct < _LIMIAR_OK:
            logger.info("%s (%s): sem maioria clara (%.1f%% em %s de %d respostas) — fica de fora.",
                        form_id, aula_do_form[form_id], pct, melhor_code, total)
            continue
        mapeados.append({
            "form_id": form_id, "projeto": projeto, "lancamento_codigo": melhor_code,
            "aula": aula_do_form[form_id], "respostas_totais": total,
            "respostas_no_lanc": melhor_n, "pct_concentracao": round(pct, 2),
        })
    return mapeados


def main() -> None:
    import yaml
    cfg_path = Path(__file__).parent.parent / "config" / "sorteio_projetos.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(DDL))

    total_mapeados = 0
    for projeto in cfg.keys():
        linhas = build_map(projeto)
        if not linhas:
            logger.info("%s: nenhum formulário com concentração >= %.0f%% num lançamento rastreado.", projeto, _LIMIAR_OK)
            continue
        with engine.begin() as conn:
            for linha in linhas:
                conn.execute(text("""
                    INSERT INTO sorteio_form_lancamento (
                        form_id, projeto, lancamento_codigo, aula,
                        respostas_totais, respostas_no_lanc, pct_concentracao, atualizado_em
                    ) VALUES (
                        :form_id, :projeto, :lancamento_codigo, :aula,
                        :respostas_totais, :respostas_no_lanc, :pct_concentracao, now()
                    )
                    ON CONFLICT (form_id) DO UPDATE SET
                        lancamento_codigo = EXCLUDED.lancamento_codigo,
                        aula               = EXCLUDED.aula,
                        respostas_totais   = EXCLUDED.respostas_totais,
                        respostas_no_lanc  = EXCLUDED.respostas_no_lanc,
                        pct_concentracao   = EXCLUDED.pct_concentracao,
                        atualizado_em      = now()
                """), linha)
        logger.info("%s: %d formulário(s) mapeado(s) a lançamento.", projeto, len(linhas))
        total_mapeados += len(linhas)

    logger.info("Total: %d formulário(s) mapeados em sorteio_form_lancamento.", total_mapeados)


if __name__ == "__main__":
    main()
