"""Confere se as correções de egress estão valendo em produção.

Responde duas perguntas com o mesmo dado:

1. **O deploy pegou?** O código antigo e o novo geram formas de consulta
   diferentes e inconfundíveis (ex: o GA4 antigo trazia linha por dia sem
   GROUP BY; o novo agrega no banco). Se as formas NOVAS aparecem e as VELHAS
   não, o container está rodando o código novo.

2. **O egress caiu?** Compara o ritmo de linhas devolvidas ao cliente com o
   que o relatório técnico mediu em 04-14/09/26 (4,93 bilhões de linhas em
   ~10 dias = ~493 milhões/dia, ~1,3 TB projetado pra 30 dias).

Uso:
    python scripts/checar_egress.py

Pré-requisito: rodar DEPOIS de um `SELECT pg_stat_statements_reset()` feito
com o código novo já no ar, e esperar algumas horas. Quanto maior a janela,
mais confiável — abaixo de 1 hora o número não significa muita coisa.

IMPORTANTE: leituras feitas da máquina local (rodar o dashboard, harness de
snapshot, scripts de teste) entram na mesma estatística e inflam o resultado.
Pra medir produção, não mexer no banco durante a janela.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from sqlalchemy import text  # noqa: E402
from frontend.db import _get_engine  # noqa: E402

# Formas de consulta que só existem numa das versões do código.
# (rótulo, condição SQL, esperado_no_codigo_novo)
ASSINATURAS = [
    ("leads: base inteira por lançamento",
     "query ILIKE '%FROM leads WHERE lancamento_codigo = $1'"
     " AND query NOT ILIKE '%COUNT%' AND query NOT ILIKE '%GROUP BY%'"
     " AND query NOT ILIKE '%ANY(%'", False),
    ("leads: agregado no banco (GROUP BY)",
     "query ILIKE '%FROM leads%' AND query ILIKE '%GROUP BY%'", True),
    ("telefones: SELECT DISTINCT \"NÚMERO\"",
     'query ILIKE \'%DISTINCT "N%MERO" FROM%\' AND query NOT ILIKE \'%norm_phone%\'', False),
    ("telefones: filtrados por norm_phone_brasil",
     "query ILIKE '%norm_phone_brasil%'", True),
    ("GA4: linha por dia (sem agregar)",
     "query ILIKE '%FROM ga4_daily%' AND query NOT ILIKE '%GROUP BY%'"
     " AND query NOT ILIKE '%SUM(%'", False),
    ("GA4: agregado por landing_page",
     "query ILIKE '%ga4_daily%' AND query ILIKE '%GROUP BY landing_page%'", True),
    ("Typeform: colunas podadas no DISTINCT ON",
     "query ILIKE '%response_id, updated_at, email%'", True),
]

# Relatório técnico de 14/09/26: 4,93 bi de linhas em ~10 dias.
BASE_LINHAS_DIA = 4_930_000_000 / 10


def main() -> int:
    with _get_engine().connect() as conn:
        # EXTRACT devolve numeric -> Decimal, que não opera com float
        horas = float(conn.execute(text(
            "SELECT EXTRACT(EPOCH FROM (now() - stats_reset)) / 3600"
            " FROM pg_stat_statements_info"
        )).scalar() or 0.0)
        _tot = conn.execute(text(
            "SELECT COALESCE(sum(rows), 0), COALESCE(sum(calls), 0)"
            " FROM pg_stat_statements WHERE query ILIKE 'select%'"
        )).fetchone()
        # sum() no Postgres devolve numeric -> Decimal, que não divide com float
        total_rows, total_calls = int(_tot[0]), int(_tot[1])

        print(f"Janela medida: {horas:.1f} h desde o reset")
        if horas < 1:
            print("  ATENÇÃO: janela curta demais pra concluir qualquer coisa.")
        print()

        print("=" * 66)
        print("1. O DEPLOY PEGOU?")
        print("=" * 66)
        veredito_ok = True
        for rotulo, cond, esperado_novo in ASSINATURAS:
            # Só SELECT: INSERT/DELETE do ETL também casam com os padrões de
            # tabela e contam linhas ESCRITAS, que não são egress. Sem este
            # filtro o DELETE FROM ga4_daily aparecia como "código antigo".
            linhas, chamadas = conn.execute(text(
                f"SELECT COALESCE(sum(rows), 0), COALESCE(sum(calls), 0)"
                f" FROM pg_stat_statements WHERE query ILIKE 'select%' AND ({cond})"
            )).fetchone()
            presente = chamadas > 0
            if esperado_novo:
                ok = presente
                nota = "esperado no código novo"
            else:
                ok = not presente
                nota = "só existe no código antigo"
            if not ok:
                veredito_ok = False
            print(f"  [{'OK ' if ok else '!! '}] {rotulo:44s} "
                  f"{chamadas:>7,} chamadas / {linhas:>12,} linhas   ({nota})")
        print()
        print("  => " + ("tudo consistente com o código novo no ar."
                         if veredito_ok else
                         "inconsistente. Formas antigas ainda aparecendo, ou novas ausentes:\n"
                         "     - se as NOVAS estão ausentes, pode ser só falta de tráfego na janela;\n"
                         "     - se as VELHAS aparecem, algum processo ainda roda o código antigo."))
        print()

        print("=" * 66)
        print("2. O EGRESS CAIU?")
        print("=" * 66)
        if horas <= 0:
            print("  sem janela medível.")
            return 0
        por_dia = total_rows / horas * 24
        print(f"  antes (relatório 04-14/09):  {BASE_LINHAS_DIA:>15,.0f} linhas/dia")
        print(f"  agora:                       {por_dia:>15,.0f} linhas/dia")
        if BASE_LINHAS_DIA:
            queda = (1 - por_dia / BASE_LINHAS_DIA) * 100
            print(f"  variação:                    {queda:>14.1f}%")
        print()
        print(f"  (total na janela: {total_rows:,} linhas em {total_calls:,} chamadas SELECT)")
        print()
        print("  Os 250 GB inclusos equivalem, na proporção do relatório")
        print("  (~430 GB para 4,93 bi de linhas), a ~2,9 bi de linhas/mês")
        print("  = ~95 milhões de linhas/dia. É essa a meta.")
        print()
        print("  Confirmação independente: painel do Supabase, Reports > Database,")
        print("  gráfico de egress por fonte — o volume deve estar em 'Shared Pooler'.")

        print()
        print("=" * 66)
        print("MAIORES CONSUMIDORES NA JANELA")
        print("=" * 66)
        for linhas, chamadas, q in conn.execute(text(
            "SELECT rows, calls, left(regexp_replace(query, '\\s+', ' ', 'g'), 92)"
            " FROM pg_stat_statements WHERE query ILIKE 'select%'"
            " ORDER BY rows DESC LIMIT 10"
        )):
            print(f"  {linhas:>12,} linhas {chamadas:>7,} ch.  {q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
