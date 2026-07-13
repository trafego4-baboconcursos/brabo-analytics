#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper fixo para gerar a analise de criativos do PES-MAI-26."""

from __future__ import annotations

import argparse

from generate_analise_criativos_launch import LaunchConfig, generate_report


DEFAULT_CONFIG = LaunchConfig(
    campaign_code="PES-MAI-26",
    campaign_folder="[PES-MAI-26]",
    product_name="Escrevente TJSP",
    period_label="Abril a Maio de 2026",
    reference_folder=None,
    output_filename="ANALISE_CRIATIVOS_[PES-MAI-26].html",
)


def build_config(output_filename: str | None = None) -> LaunchConfig:
    if output_filename:
        return LaunchConfig(
            campaign_code=DEFAULT_CONFIG.campaign_code,
            campaign_folder=DEFAULT_CONFIG.campaign_folder,
            product_name=DEFAULT_CONFIG.product_name,
            period_label=DEFAULT_CONFIG.period_label,
            reference_folder=DEFAULT_CONFIG.reference_folder,
            output_filename=output_filename,
        )
    return DEFAULT_CONFIG


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wrapper fixo da analise de criativos PES-MAI-26")
    parser.add_argument(
        "--output-filename",
        help="Nome opcional do arquivo HTML de saida dentro de analises/[PES-MAI-26]/",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = build_config(args.output_filename)
    generate_report(config)


if __name__ == "__main__":
    main()