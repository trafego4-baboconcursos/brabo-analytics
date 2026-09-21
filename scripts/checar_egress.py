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

# Aviso amigavel em vez de ModuleNotFoundError cru: e facil rodar com o Python
# do sistema em vez do da .venv, e o traceback do `dotenv` nao diz o que fazer.
try:
    from dotenv import load_dotenv  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - depende do ambiente
    _venv = Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe"
    raise SystemExit(
        "Este script precisa do Python do projeto (.venv), nao o do sistema.\n"
        f"  PowerShell:  {_venv} scripts/checar_egress.py\n"
        "  ou ative a venv uma vez:  .\\.venv\\Scripts\\Activate.ps1"
    ) from None
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
    # A poda de colunas do DISTINCT ON foi substituida em 18/09 pela tabela
    # materializada: a assinatura antiga virou alarme falso (zero chamadas
    # porque a consulta deixou de existir, nao porque o deploy falhou).
    # O `count(*)` de _contar_respostas_brutas usa a forma antiga de proposito —
    # total_tf_raw conta a fonte original, incluindo resposta sem e-mail valido,
    # que a tabela materializada nao tem. Devolve 1 linha, entao nao e egress.
    ("Typeform: SELECT * com answers cru",
     "query ILIKE '%DISTINCT ON (response_id)%' AND query ILIKE '%SELECT * FROM typeform_respostas %'"
     " AND query NOT ILIKE '%count(*)%'", False),
    ("Typeform: le a tabela materializada",
     "query ILIKE '%typeform_respostas_valores%'", True),
]

# Relatório técnico de 14/09/26: 4,93 bi de linhas em ~10 dias.
BASE_LINHAS_DIA = 4_930_000_000 / 10


# Bytes por linha, medidos com octet_length em 18/09/26. Sem isto o script ordena
# por NÚMERO DE LINHAS e aponta o alvo errado — foi o que aconteceu em 17/09,
# quando read_meta liderava com 51 milhões de linhas de 333 bytes e o Typeform,
# com menos linhas de 4,8 KB, custava 7x mais.
_PESOS = (
    ("typeform_respostas_valores", 951),   # materializada, só os valores
    ("typeform_respostas", 4844),          # `answers` cru, com metadado do Typeform
    ("jsonb_object_agg", 1309),            # pesquisa nova, uma linha por submissão
    ("submissoes", 1309),
    ("meta_ads_daily", 333),
    ("google_ads_daily", 333),
    ("meta_ads_region_daily", 115),
    ("email_norm", 37),
    ("FROM leads", 120),
)
_PESO_PADRAO = 100


def _peso_da_linha(consulta: str) -> int:
    """Bytes por linha estimados pela tabela/coluna que a consulta toca.

    Casa na ordem de _PESOS — o mais específico vem antes
    (typeform_respostas_valores antes de typeform_respostas).
    """
    alvo = consulta.lower()
    for padrao, peso in _PESOS:
        if padrao.lower() in alvo:
            return peso
    return _PESO_PADRAO


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
        print("  ATENÇÃO: egress é BYTE, não linha. Uma linha de `answers` (jsonb) pesa")
        print("  ~4,8 KB; uma de meta_ads_daily pesa 333 bytes — 14x menos. A coluna de")
        print("  peso abaixo corrige isso (medições de 18/09/26, octet_length real).")
        print()
        for linhas, chamadas, q in conn.execute(text(
            # Consulta INTEIRA aqui: o peso é casado pelo texto, e truncar antes
            # de casar fazia "typeform_respostas" cair fora do corte e a linha
            # pesada ser contada como leve. O corte fica só na hora de imprimir.
            r"SELECT rows, calls, regexp_replace(query, '\s+', ' ', 'g')"
            " FROM pg_stat_statements WHERE query ILIKE 'select%'"
            " ORDER BY rows DESC LIMIT 10"
        )):
            gb = linhas * _peso_da_linha(q) / 1e9 / max(horas, 1) * 24
            print(f"  {linhas:>12,} lin {chamadas:>6,} ch {gb:>7.2f} GB/dia  {q[:66]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
