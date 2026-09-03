"""
Script para gerar arquivo de público para upload no Google Ads (Customer Match)
a partir do CSV exportado do Active Campaign.

Formato de saída:
- Email, First Name, Last Name, Phone, Zip, Country
- Padrão Google Ads Customer Match (texto plano — o próprio Google faz o hash)
- Telefones normalizados para E.164 (ex: +5511999999999)
"""

import csv
import re
import os

# Caminho do arquivo de entrada
INPUT_FILE = r"C:\dev\workspace-mmm\analises\[PES-MAI-26]\Active Campaign\active-campaign-pes-mai-26.csv"

# Caminho do arquivo de saída
OUTPUT_FILE = r"C:\dev\workspace-mmm\analises\[PES-MAI-26]\Active Campaign\google-ads-audience-pes-mai-26.csv"


def normalize_phone(phone_raw: str) -> str:
    """
    Normaliza número de telefone para formato E.164 brasileiro.
    Ex: (11) 9 9999-9999 → +5511999999999
    """
    if not phone_raw:
        return ""

    # Remove tudo que não é dígito
    digits = re.sub(r"\D", "", phone_raw)

    # Se já tiver código do país Brasil (55) no início
    if digits.startswith("55") and len(digits) >= 12:
        return f"+{digits}"

    # Adiciona o código do país Brasil
    if len(digits) >= 10:
        return f"+55{digits}"

    return ""  # Número inválido, retorna vazio


def normalize_name(name_raw: str) -> str:
    """Remove espaços extras e padroniza capitalização."""
    if not name_raw:
        return ""
    return name_raw.strip().title()


def normalize_email(email_raw: str) -> str:
    """Normaliza o email para minúsculas e sem espaços."""
    if not email_raw:
        return ""
    return email_raw.strip().lower()


def main():
    total_input = 0
    total_output = 0
    skipped_no_email = 0

    print(f"Lendo arquivo: {INPUT_FILE}")
    print("Gerando arquivo de público para Google Ads...")

    with open(INPUT_FILE, "r", encoding="utf-8", errors="replace") as infile, \
         open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as outfile:

        reader = csv.DictReader(infile)
        writer = csv.writer(outfile)

        # Cabeçalho exigido pelo Google Ads Customer Match
        writer.writerow(["Email", "First Name", "Last Name", "Phone", "Zip", "Country"])

        for row in reader:
            total_input += 1

            email = normalize_email(row.get("Email", ""))

            # Pula registros sem email (campo obrigatório para Customer Match)
            if not email:
                skipped_no_email += 1
                continue

            first_name = normalize_name(row.get("Nome", ""))
            last_name = normalize_name(row.get("Sobrenome", ""))

            # Tenta o campo "Número de telefone"
            phone_raw = row.get("Número de telefone", "") or ""
            phone = normalize_phone(phone_raw)

            # País padrão: Brasil
            country = "BR"

            writer.writerow([email, first_name, last_name, phone, "", country])
            total_output += 1

            # Progress log a cada 50.000 registros
            if total_input % 50000 == 0:
                print(f"  Processados: {total_input:,} registros...")

    print("\n Arquivo gerado com sucesso!")
    print(f"   Registros lidos:       {total_input:,}")
    print(f"   Registros exportados:  {total_output:,}")
    print(f"   Ignorados (sem email): {skipped_no_email:,}")
    print(f"\nArquivo salvo em:\n   {OUTPUT_FILE}")


if __name__ == "__main__":
    main()