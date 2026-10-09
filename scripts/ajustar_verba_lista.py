"""Aplica a verba diária de uma lista de campanhas (Meta + Google) e confere relendo da plataforma.

A lista vive em config/orcamentos/<ARQUIVO>.json (rastreado pelo git — não pode ficar em pasta ignorada, senão o
GitHub Actions não enxerga; ver memória feedback_git_ignore_breaks_automation):

    {"aplicar_em": "2026-10-09",
     "campanhas": [{"plataforma": "meta"|"google", "conta": "<customer id, só Google>", "id": "...", "nome": "...", "valor": 1136.0}]}

Uso:
    python -m scripts.ajustar_verba_lista --arquivo config/orcamentos/BV-26-captacao-v2.json --dry-run   # só lê e compara
    python -m scripts.ajustar_verba_lista --arquivo config/orcamentos/BV-26-captacao-v2.json             # aplica (só na data do plano)
    python -m scripts.ajustar_verba_lista --arquivo ... --forcar                                          # aplica em qualquer dia

Regras:
- só aplica no dia `aplicar_em` (fuso de Brasília): um cron anual não pode repetir a verba de outro dia;
- **sai com código 1 se qualquer campanha falhar** (erro de API ou valor lido ≠ valor pedido), para o job do GitHub ficar vermelho;
- Meta: CBO na campanha (`Meta.definir_verba_diaria`); Google: orçamento próprio (`Google.definir_verba_diaria`, que recusa orçamento
  compartilhado e campanha VIDEO).
Precisa de META_ACCESS_TOKEN e GOOGLE_ADS_* no ambiente (.env local ou secrets do Actions).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

BRASILIA = dt.timezone(dt.timedelta(hours=-3))


def ler_plano(caminho: str | Path) -> dict:
    """Lê e valida o plano. Levanta ValueError com a campanha problemática."""
    plano = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if not plano.get("aplicar_em"):
        raise ValueError("plano sem 'aplicar_em'")
    dt.date.fromisoformat(plano["aplicar_em"])
    camps = plano.get("campanhas") or []
    if not camps:
        raise ValueError("plano sem campanhas")
    vistos = set()
    for c in camps:
        quem = f"{c.get('plataforma')}:{c.get('id')}"
        if c.get("plataforma") not in ("meta", "google"):
            raise ValueError(f"{quem}: plataforma inválida")
        if not str(c.get("id", "")).isdigit():
            raise ValueError(f"{quem}: id inválido")
        if c["plataforma"] == "google" and not str(c.get("conta", "")).isdigit():
            raise ValueError(f"{quem}: Google exige 'conta'")
        if not isinstance(c.get("valor"), (int, float)) or c["valor"] <= 0:
            raise ValueError(f"{quem}: valor inválido")
        if quem in vistos:
            raise ValueError(f"{quem}: repetida")
        vistos.add(quem)
    return plano


def hoje_brasilia(agora: dt.datetime | None = None) -> dt.date:
    return (agora or dt.datetime.now(dt.timezone.utc)).astimezone(BRASILIA).date()


def deve_aplicar(plano: dict, hoje: dt.date, forcar: bool = False) -> bool:
    return forcar or dt.date.fromisoformat(plano["aplicar_em"]) == hoje


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arquivo", required=True)
    ap.add_argument("--dry-run", action="store_true", help="só lê as verbas atuais e compara; não grava")
    ap.add_argument("--forcar", action="store_true", help="ignora a data do plano")
    args = ap.parse_args(argv)

    plano = ler_plano(args.arquivo)
    hoje = hoje_brasilia()
    if not args.dry_run and not deve_aplicar(plano, hoje, args.forcar):
        print(f"Hoje é {hoje}; o plano é para {plano['aplicar_em']}. Nada a fazer (use --forcar para ignorar).")
        return 0

    from scripts.ads.google import Google
    from scripts.ads.meta import Meta

    meta, google = Meta(), Google()
    falhas, linhas = [], []
    for c in plano["campanhas"]:
        quem = f"{c['plataforma']:6} {c['id']:>20}  {c['nome'][:75]}"
        try:
            if c["plataforma"] == "meta":
                atual = int(meta.get(c["id"], fields="daily_budget")["daily_budget"]) / 100
                if not args.dry_run:
                    meta.definir_verba_diaria(c["id"], c["valor"])
                    atual_depois = int(meta.get(c["id"], fields="daily_budget")["daily_budget"]) / 100
            else:
                conta = c["conta"]
                def ler():
                    r = google.buscar(conta, f"SELECT campaign_budget.amount_micros FROM campaign WHERE campaign.id = {c['id']}")
                    return int(r[0]["campaignBudget"]["amountMicros"]) / 1e6
                atual = ler()
                if not args.dry_run:
                    google.definir_verba_diaria(conta, c["id"], c["valor"])
                    atual_depois = ler()
            if args.dry_run:
                linhas.append(f"[dry-run] {quem}  {atual:>9.2f} -> {c['valor']:>9.2f}")
            elif abs(atual_depois - c["valor"]) > 0.02:
                raise RuntimeError(f"lido R$ {atual_depois:.2f} ≠ pedido R$ {c['valor']:.2f}")
            else:
                linhas.append(f"[ok]      {quem}  {atual:>9.2f} -> {atual_depois:>9.2f}")
        except Exception as e:  # noqa: BLE001 — qualquer erro vira falha do job
            falhas.append(f"{quem}: {e}")
            linhas.append(f"[ERRO]    {quem}: {e}")
    print("\n".join(linhas))
    total = sum(c["valor"] for c in plano["campanhas"])
    print(f"\n{len(plano['campanhas'])} campanhas, total pedido R$ {total:,.2f}/dia; falhas: {len(falhas)}")
    if falhas:
        print("\nFALHARAM:\n" + "\n".join(falhas), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
