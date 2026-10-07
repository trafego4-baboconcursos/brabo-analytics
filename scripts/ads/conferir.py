"""Checklist do padrão da casa em todas as campanhas de um lançamento (Meta + Google), só leitura.

    python -m scripts.ads.conferir BV-26
    python -m scripts.ads.conferir BV-26 --so-ativas

Confere, por campanha: no Meta, idade 25–55, advantage declarado, data de fim, Reels sem Feed, pixel no
tracking_specs, UTM padrão em url_tags e link limpo; no Google, orçamento próprio, data de fim, tracking
template, parâmetros personalizados nos 3 níveis e região no grupo (público agrupado). Não altera nada.
"""
from __future__ import annotations

import argparse
import sys

from scripts.ads import padroes as P
from scripts.ads.google import Google
from scripts.ads.meta import Meta, expert_do_nome, problemas_adset, problemas_anuncios

CONTAS_META = [P.META_CONTAS["ca2_anunciante"], P.META_CONTAS["felipe_nova"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lancamento")
    ap.add_argument("--so-ativas", action="store_true")
    a = ap.parse_args()
    total = 0

    m = Meta()
    for conta in CONTAS_META:
        for c in m.campanhas(conta, a.lancamento):
            if a.so_ativas and c["effective_status"] != "ACTIVE":
                continue
            expert = expert_do_nome(c["name"])
            probs = []
            for s in m.adsets(c["id"]):
                probs += problemas_adset(s, c["name"])
            if expert:
                probs += problemas_anuncios(m.anuncios(c["id"]), P.META_EXPERTS[expert]["pixel_id"])
            else:
                probs.append("nome sem tag de expert ([mateus]/[ivan]/[felipe]) — pixel não conferido")
            total += len(probs)
            print(f"[{'OK' if not probs else '!!'}] Meta {c['name']}")
            for p in probs:
                print(f"      - {p}")

    g = Google()
    for conta in P.GOOGLE_CONTAS.values():
        for c in g.campanhas(conta, a.lancamento):
            if a.so_ativas and c["status"] != "ENABLED":
                continue
            probs = g.conferir_campanha(conta, c["id"])
            total += len(probs)
            aviso = " (VIDEO: ajuste só manual)" if c.get("advertisingChannelType") == "VIDEO" else ""
            print(f"[{'OK' if not probs else '!!'}] Google {c['name']}{aviso}")
            for p in probs:
                print(f"      - {p}")

    print(f"\n{total} ponto(s) fora do padrão.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
