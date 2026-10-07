"""Congela a atribuição de um lançamento — ou de todos — na tabela
`atribuicao_congelada`.

POR QUE: a `leads` tem UMA linha por contato e um `lancamento_codigo` só.
Quando a pessoa se cadastra num lançamento novo, a linha é reescrita e o
lançamento antigo perde aquele comprador junto com a UTM que o trouxe. Em
07/10/26 todo lançamento fechado já tinha perdido de 32% a 41% dos compradores
rastreados. Ver seção 13 de `docs/sistema/METODOLOGIA_EXTRACAO_DADOS.md`.

A gravação é monotônica (só sobrescreve com score MAIOR), então rodar de novo
nunca piora o que já está congelado. Rodar com frequência é seguro e é o
recomendado: cada rodada trava o que ainda não foi perdido.

Uso:
    python scripts/congelar_atribuicao.py --launch PI-AGO-26
    python scripts/congelar_atribuicao.py --todos
    python scripts/congelar_atribuicao.py --todos --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))
sys.path.insert(0, str(_RAIZ / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_RAIZ / ".env")


def _congelar(code: str, dry_run: bool) -> tuple[int, int, int]:
    """Devolve (compradores, rastreados_ao_vivo, linhas_enviadas)."""
    from frontend.core import get_launches  # noqa: PLC0415
    from frontend.db_readers import read_vendas  # noqa: PLC0415
    from frontend.services.attribution import _sales_attribution  # noqa: PLC0415
    from frontend.db_readers.atribuicao_congelada import (  # noqa: PLC0415
        gravar_congelada, ler_congelada,
    )

    launch = next((x for x in get_launches() if x.code == code), None)
    if launch is None:
        print(f"  {code}: lançamento não encontrado")
        return 0, 0, 0

    vendas = read_vendas(code)
    if vendas is None:
        # Lançamento ainda sem venda (carrinho não abriu) ou sem config de
        # produto. Não há o que congelar, e não é erro.
        print(f"  {code:14s} sem vendas — nada a congelar")
        return 0, 0, 0
    compradores = len(vendas.emails_hotmart | vendas.emails_tmb)
    antes = len(ler_congelada(code))

    # O _sales_attribution já aplica a trava existente, então o que ele devolve
    # é a melhor visão disponível hoje: ao vivo + o que já estava congelado.
    attr = _sales_attribution(launch, vendas, devolver_utms=True)
    buyer_utms = attr.get("_buyer_utms") or {}
    rastreados = len(attr.get("emails_rastreados") or ())

    if dry_run:
        print(f"  {code:14s} compradores={compradores:>5} rastreados={rastreados:>5} "
              f"congelados_antes={antes:>5}  (dry-run, nada gravado)")
        return compradores, rastreados, 0

    enviadas = gravar_congelada(code, buyer_utms)
    depois = len(ler_congelada(code))
    print(f"  {code:14s} compradores={compradores:>5} rastreados={rastreados:>5} "
          f"congelados {antes:>5} -> {depois:>5}  (+{depois - antes})")
    return compradores, rastreados, enviadas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--launch", help="código do lançamento (ex: PI-AGO-26)")
    ap.add_argument("--todos", action="store_true", help="todos os lançamentos conhecidos")
    ap.add_argument("--dry-run", action="store_true", help="só relata, não grava")
    args = ap.parse_args()

    if not args.launch and not args.todos:
        ap.error("informe --launch CODE ou --todos")

    from frontend.core import get_launches  # noqa: PLC0415

    codes = [args.launch] if args.launch else [x.code for x in get_launches()]
    print(f"congelando atribuição de {len(codes)} lançamento(s)"
          f"{' (dry-run)' if args.dry_run else ''}:")
    falhas = 0
    for code in codes:
        try:
            _congelar(code, args.dry_run)
        except Exception as e:  # noqa: BLE001 — um lançamento ruim não para os outros
            falhas += 1
            print(f"  {code:14s} ERRO: {type(e).__name__}: {e}")
    if falhas:
        print(f"\n{falhas} lançamento(s) falharam.")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
