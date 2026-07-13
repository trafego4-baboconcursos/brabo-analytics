#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import runpy
from pathlib import Path


BASE = Path(r"c:\Users\trafe\OneDrive\Desktop\workspace-mmm")


if __name__ == "__main__":
    runpy.run_path(
        str(BASE / "scripts-python" / "generate_analise_vendas_final.py"),
        run_name="__main__",
        init_globals={
            "BASE": BASE,
            "CAMPAIGN_CODE": "PBB-ABR-26",
            "CAMPAIGN_FOLDER": "[PBB-ABR-26]",
            "ACTIVE_FOLDER": "Active Campaign",
            "TYPEFORM_FOLDER": "Typeform",
            "VENDAS_FOLDER": "Vendas",
            "HOTMART_FILE": "hotmart pbb-abr-26.csv",
            "TMB_FILE": "tmb pbb-abr-26.csv",
            "OUTPUT_FILE": "ANALISE_VENDAS_[PBB-ABR-26].html",
        },
    )