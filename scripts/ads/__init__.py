"""Operação de campanhas (Meta e Google) com os padrões da casa embutidos.

- padroes.py — valores fixos: contas, pixels, páginas, UTM, idade, geo, regulação, pisos de verba.
- meta.py    — cliente da Marketing API + operações seguras (targeting, status, verba, fim, públicos, criação).
- google.py  — cliente REST do Google Ads + Data Manager (status, verba, fim, listas, exclusão, Customer Match).
- conferir.py — checklist de um lançamento inteiro: `python -m scripts.ads.conferir BV-26`.

Manual de uso e o porquê de cada regra: docs/performance/playbooks/MANUAL_OPERACAO_ADS.md
"""
