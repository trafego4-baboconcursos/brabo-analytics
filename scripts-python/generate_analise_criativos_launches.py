#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orquestrador dos wrappers fixos de criativos por lançamento."""

from __future__ import annotations

import argparse

from generate_analise_criativos_launch import LaunchConfig, generate_report


LAUNCHES: dict[str, LaunchConfig] = {
    "PBB-ABR-26": LaunchConfig(
        campaign_code="PBB-ABR-26",
        campaign_folder="[PBB-ABR-26]",
        product_name="Banco do Brasil",
        period_label="Abril de 2026",
        reference_folder="[PBB-FEV-26]",
        output_filename="ANALISE_CRIATIVOS_[PBB-ABR-26].html",
    ),
    "PBB-FEV-26": LaunchConfig(
        campaign_code="PBB-FEV-26",
        campaign_folder="[PBB-FEV-26]",
        product_name="Banco do Brasil",
        period_label="Fevereiro de 2026",
        reference_folder=None,
        output_filename="ANALISE_CRIATIVOS_[PBB-FEV-26].html",
    ),
    "PES-MAI-26": LaunchConfig(
        campaign_code="PES-MAI-26",
        campaign_folder="[PES-MAI-26]",
        product_name="Escrevente TJSP",
        period_label="Abril a Maio de 2026",
        reference_folder=None,
        output_filename="ANALISE_CRIATIVOS_[PES-MAI-26].html",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera analises de criativos por lançamento")
    parser.add_argument(
        "--launch",
        choices=sorted(LAUNCHES.keys()),
        help="Gera apenas um lançamento específico",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Gera todos os lançamentos registrados neste orquestrador",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.launch and not args.all:
        raise SystemExit("Use --launch <codigo> ou --all")

    targets = [args.launch] if args.launch else list(LAUNCHES.keys())
    for launch_code in targets:
        generate_report(LAUNCHES[launch_code])


if __name__ == "__main__":
    main()