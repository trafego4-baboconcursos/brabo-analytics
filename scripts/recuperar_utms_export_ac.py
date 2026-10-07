"""Recupera UTMs perdidas a partir do export do Active Campaign **da época**.

POR QUE EXISTE: a `leads` tem uma linha por contato; quando a pessoa entra num
lançamento novo, a linha é reescrita e o lançamento antigo perde o comprador
junto com a UTM que o trouxe (seção 13 de
`docs/sistema/METODOLOGIA_EXTRACAO_DADOS.md`). A trava
(`scripts/congelar_atribuicao.py`) impede perdas NOVAS, mas não traz de volta o
que já tinha sumido quando ela entrou, em 07/10/26.

Os CSV em `analises/[LANC]/Active Campaign/` são exports do AC tirados **durante
ou logo após** cada lançamento — e trazem a UTM como ela estava naquele dia.

A REGRA ESTRITA: só recupera a UTM que **nomeia o lançamento**. O export tem o
mesmo problema de sobrescrita, só congelado mais cedo: medido no PI-AGO-26, dos
639 compradores achados no export, 110 carregavam UTM de OUTRO lançamento e
seriam creditados ao anúncio errado; 119 não tinham código nenhum e não dá pra
afirmar nada; 35 vinham com `{{campaign.name}}` não resolvido. Sobram 324 com
origem comprovável — e é só esses que este script grava.

O que entra fica marcado com `origem='export_ac'` na tabela, porque é história
remontada, não medida do dia.

Uso:
    python scripts/recuperar_utms_export_ac.py --launch PI-AGO-26 --dry-run
    python scripts/recuperar_utms_export_ac.py --launch PI-AGO-26
    python scripts/recuperar_utms_export_ac.py --todos --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_RAIZ))
sys.path.insert(0, str(_RAIZ / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_RAIZ / ".env")

_TAMANHO_BLOCO = 100_000


def _exports(code: str) -> list[Path]:
    pasta = _RAIZ / "analises" / f"[{code}]" / "Active Campaign"
    return sorted(pasta.glob("*.csv")) if pasta.is_dir() else []


def _norm_coluna(c: str) -> str:
    """`*Utm_campaign`, `Utm_campaign` e `utm_campaign` são a mesma coluna —
    o formato do export do AC mudou entre lançamentos."""
    return re.sub(r"[^a-z_]", "", str(c).lower().replace("*", "").strip())


def _recuperar(code: str, dry_run: bool) -> int:
    import pandas as pd  # noqa: PLC0415
    from frontend.db_readers import read_vendas  # noqa: PLC0415
    from frontend.db_readers.atribuicao_congelada import (  # noqa: PLC0415
        gravar_congelada, ler_congelada,
    )
    from frontend.services.attribution import _utm_score  # noqa: PLC0415
    from frontend.utils import _norm_text  # noqa: PLC0415

    arquivos = _exports(code)
    if not arquivos:
        print(f"  {code:14s} sem export do AC em analises/[{code}]/Active Campaign/")
        return 0

    vendas = read_vendas(code)
    if vendas is None:
        print(f"  {code:14s} sem vendas — nada a recuperar")
        return 0
    compradores = {e.strip().lower() for e in (vendas.emails_hotmart | vendas.emails_tmb)}
    faltam = compradores - set(ler_congelada(code))
    if not faltam:
        print(f"  {code:14s} nada faltando — {len(compradores)} compradores já travados")
        return 0

    alvo = _norm_text(code)
    achados: dict[str, dict] = {}
    for arq in arquivos:
        for bloco in pd.read_csv(arq, chunksize=_TAMANHO_BLOCO, dtype=str,
                                 on_bad_lines="skip", low_memory=False,
                                 encoding="utf-8-sig"):
            bloco.columns = [_norm_coluna(c) for c in bloco.columns]
            if "email" not in bloco.columns:
                continue
            bloco["_e"] = bloco["email"].astype(str).str.strip().str.lower()
            for _, linha in bloco[bloco["_e"].isin(faltam)].iterrows():
                email = linha["_e"]
                if email in achados:
                    continue
                utm = {}
                for campo in ("source", "medium", "campaign", "content", "term"):
                    val = str(linha.get(f"utm_{campo}") or "").strip()
                    utm[campo] = "" if val.lower() == "nan" else val
                achados[email] = utm

    bons: dict[str, dict] = {}
    # "nao_nomeia_o_lancamento" junta dois casos que dão no mesmo: UTM de outro
    # lançamento e UTM sem código nenhum. Nos dois não dá pra afirmar que foi
    # este lançamento que trouxe a pessoa, então nos dois a linha é descartada.
    descartados = {"nao_nomeia_o_lancamento": 0, "template": 0, "sem_utm": 0}
    for email, utm in achados.items():
        if not (utm["source"] or utm["medium"] or utm["campaign"]):
            descartados["sem_utm"] += 1
            continue
        if "{{" in utm["campaign"] or "{{" in utm["content"]:
            descartados["template"] += 1  # merge tag do AC que nunca resolveu
            continue
        if alvo not in _norm_text(" ".join(utm.values())):
            descartados["nao_nomeia_o_lancamento"] += 1
            continue
        utm["score"] = _utm_score(code, utm["source"], utm["medium"],
                                  utm["campaign"], utm["content"], utm["term"])
        bons[email] = utm

    print(f"  {code:14s} faltavam={len(faltam):>5} achados_no_export={len(achados):>5} "
          f"recuperáveis={len(bons):>5} descartados={sum(descartados.values()):>5} "
          f"{descartados}")
    if dry_run or not bons:
        return 0
    gravar_congelada(code, bons, origem="export_ac")
    depois = len(ler_congelada(code))
    print(f"  {code:14s} -> travados agora: {depois}")
    return len(bons)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--launch")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.launch and not args.todos:
        ap.error("informe --launch CODE ou --todos")

    from frontend.core import get_launches  # noqa: PLC0415

    codes = [args.launch] if args.launch else [x.code for x in get_launches()]
    print(f"recuperando UTMs de {len(codes)} lançamento(s)"
          f"{' (dry-run)' if args.dry_run else ''}:")
    total = 0
    for code in codes:
        try:
            total += _recuperar(code, args.dry_run)
        except Exception as e:  # noqa: BLE001
            print(f"  {code:14s} ERRO: {type(e).__name__}: {e}")
    print(f"\ntotal recuperado: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
