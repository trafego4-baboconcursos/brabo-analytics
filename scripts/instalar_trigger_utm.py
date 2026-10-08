"""Instala (ou remove) o trigger do histórico de UTM na tabela `leads` do banco REAL.

NÃO roda sozinho em nenhum lugar: é um comando manual, com o ok de quem decide. Antes
de instalar, o código foi testado numa transação desfeita (`tests/test_trigger_utm.py`).
O que o trigger faz e por quê: ver `etl/historico_utm_trigger.py`.

    python scripts/instalar_trigger_utm.py --dry-run     # só mostra o que faria
    python scripts/instalar_trigger_utm.py --instalar
    python scripts/instalar_trigger_utm.py --verificar   # fumaça: grava e DESFAZ
    python scripts/instalar_trigger_utm.py --remover     # botão de emergência (as tabelas ficam)
    python scripts/instalar_trigger_utm.py --visao       # cria/atualiza a visão leads_por_lancamento
    python scripts/instalar_trigger_utm.py --reverter-visao   # a visão volta a ser a própria leads

CUIDADOS DE PRODUÇÃO
  - `CREATE TRIGGER` pede um lock na `leads` que espera as gravações em andamento
    terminarem, e o ETL grava em transações de vários minutos. Por isso `lock_timeout`
    curto e nova tentativa: se não conseguir agora, desiste em 5 s e tenta de novo, em
    vez de ficar na fila segurando quem escreve atrás.
  - Tudo (tabelas, funções, triggers) vai numa transação só: ou instala completo ou
    não instala nada.
  - `SET LOCAL`, nunca `SET`: a conexão volta para o pool e carregaria o timeout.
  - Enquanto o ETL de produção ainda tiver o passo antigo `gravar_historico_antes`, ele
    grava o estado ANTES da `leads`, e o trigger não vê a troca de UTM vinda do ETL
    (só a vinda de outros escritores). Remover aquele passo e fazer o deploy do ETL
    fecha essa janela.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ / "src"))
sys.path.insert(0, str(_RAIZ / "etl"))
sys.path.insert(0, str(_RAIZ))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_RAIZ / ".env")

import psycopg2.errors  # noqa: E402

import historico_utm_trigger as ht  # noqa: E402

N = ht.Nomes()          # nomes reais
TENTATIVAS = 10
ESPERA_S = 20


def _executar(comandos: list[str]) -> None:
    from frontend.db import _get_engine  # noqa: PLC0415

    for tentativa in range(1, TENTATIVAS + 1):
        conn = _get_engine().raw_connection()
        try:
            cur = conn.cursor()
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute("SET LOCAL statement_timeout = '120s'")
            for comando in comandos:
                cur.execute(comando)
            conn.commit()
            print(f"  ok (tentativa {tentativa})")
            return
        except psycopg2.errors.LockNotAvailable:
            conn.rollback()
            print(f"  tentativa {tentativa}/{TENTATIVAS}: a leads está ocupada, nova tentativa em {ESPERA_S}s")
            time.sleep(ESPERA_S)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    raise SystemExit("não consegui o lock na leads — nada foi alterado. Tente em um momento de menos carga.")


def verificar() -> bool:
    """Fumaça no trigger REAL: grava um contato sintético e DESFAZ no fim."""
    from frontend.db import _get_engine  # noqa: PLC0415

    camp1 = "[MA][cadastro][captação][PI-AGO-26][20.07.26]"
    camp2 = "[GA][captação][PI-AGO-26][27.07.26]"
    conn = _get_engine().raw_connection()
    ok = True
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM pg_trigger WHERE tgrelid = 'public.leads'::regclass "
                    "AND tgname IN (%s, %s)", (N.trg_ins, N.trg_upd))
        n_trg = cur.fetchone()[0]
        print(f"  triggers instalados na leads: {n_trg} de 2")
        if n_trg != 2:
            # Sem o trigger não há o que verificar — e não vale nem encostar na leads.
            print("  triggers não instalados: nada a verificar (rode --instalar)")
            return False
        ok &= n_trg == 2
        upsert = (f"INSERT INTO {N.leads} (id, email, utm_source, utm_medium, utm_campaign, utm_content, utm_term) "
                  "VALUES ('zz-fumaca', 'fumaca@teste.invalid', 'facebook', 'cpc', %s, %s, '') "
                  "ON CONFLICT (id) DO UPDATE SET utm_campaign = EXCLUDED.utm_campaign, utm_content = EXCLUDED.utm_content")
        cur.execute(upsert, (camp1, "AD100"))
        cur.execute(f"SELECT count(*) FROM {N.estado} WHERE contact_id = 'zz-fumaca'")
        a = cur.fetchone()[0]
        cur.execute(upsert, (camp2, "AD400"))
        cur.execute(f"SELECT utm_content FROM {N.estado} WHERE contact_id = 'zz-fumaca'")
        atual = cur.fetchone()[0]
        cur.execute(f"SELECT utm_content FROM {N.historico} WHERE contact_id = 'zz-fumaca'")
        hist = [r[0] for r in cur.fetchall()]
        print(f"  cadastro novo entrou no estado: {a == 1} | UTM atual: {atual} | histórico guardou: {hist}")
        ok &= a == 1 and atual == "AD400" and hist == ["AD100"]
    finally:
        conn.rollback()      # o contato sintético NUNCA fica
        conn.close()
    print("  (contato sintético desfeito)")
    return bool(ok)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--instalar", action="store_true")
    g.add_argument("--verificar", action="store_true")
    g.add_argument("--remover", action="store_true")
    g.add_argument("--visao", action="store_true")
    g.add_argument("--reverter-visao", dest="reverter_visao", action="store_true")
    a = ap.parse_args()

    if a.dry_run:
        cmds = ht.ddl_completo(N)
        print(f"{len(cmds)} comandos numa transação só, na ordem:")
        for c in cmds:
            print("  -", c.strip().splitlines()[0][:110])
        return 0
    if a.instalar:
        print("instalando o trigger de histórico de UTM...")
        _executar(ht.ddl_completo(N))
        print("verificando...")
        return 0 if verificar() else 1
    if a.verificar:
        return 0 if verificar() else 1
    if a.visao:
        print("criando a visão leads_por_lancamento (só leitura: nenhuma tabela muda)...")
        _executar([ht.ddl_visao(N)])
        return 0
    if a.reverter_visao:
        print("revertendo: leads_por_lancamento volta a ser a própria leads...")
        _executar([ht.ddl_visao_reverter(N)])
        return 0
    print("removendo os triggers (as tabelas e os dados ficam)...")
    _executar(ht.ddl_remover(N))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
