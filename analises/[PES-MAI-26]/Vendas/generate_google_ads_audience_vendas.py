"""
Script para gerar arquivo de público de COMPRADORES (Hotmart + TMB) para
upload no Google Ads (Customer Match) — PES-MAI-26.

Combina as duas listas de vendas em um único público, removendo duplicatas
de email entre as fontes e transações canceladas.

Formato de saída (padrão Google Ads Customer Match):
- Email, First Name, Last Name, Phone, Zip, Country
- Telefones normalizados para E.164 (ex: +5511999999999)
"""

import csv
import re

HOTMART_FILE = r"C:\dev\workspace-mmm\analises\[PES-MAI-26]\Vendas\hotmart-pes-mai-26.csv"
TMB_FILE = r"C:\dev\workspace-mmm\analises\[PES-MAI-26]\Vendas\tmb-pes-mai-26.csv"
OUTPUT_FILE = r"C:\dev\workspace-mmm\analises\[PES-MAI-26]\Vendas\google-ads-audience-vendas-pes-mai-26.csv"

# Status que indicam venda cancelada/não confirmada — não entram no público
TMB_STATUS_EXCLUIR = {"Cancelado", "Cancelamento solicitado"}


def normalize_phone(phone_raw: str) -> str:
    """Normaliza número de telefone para formato E.164 brasileiro."""
    if not phone_raw:
        return ""

    digits = re.sub(r"\D", "", phone_raw)

    if digits.startswith("55") and len(digits) >= 12:
        return f"+{digits}"

    if len(digits) >= 10:
        return f"+55{digits}"

    return ""


def normalize_name_parts(full_name_raw: str) -> tuple[str, str]:
    """Separa nome completo em primeiro nome e sobrenome, com capitalização padronizada."""
    if not full_name_raw:
        return "", ""
    parts = full_name_raw.strip().title().split()
    if not parts:
        return "", ""
    first_name = parts[0]
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    return first_name, last_name


def normalize_email(email_raw: str) -> str:
    if not email_raw:
        return ""
    return email_raw.strip().lower()


def normalize_zip(zip_raw: str) -> str:
    if not zip_raw:
        return ""
    digits = re.sub(r"\D", "", zip_raw)
    return digits


def main():
    seen_emails = set()
    rows_out = []

    total_hotmart = 0
    total_tmb = 0
    skipped_no_email = 0
    skipped_duplicate = 0
    skipped_tmb_cancelado = 0

    # --- Hotmart ---
    print(f"Lendo arquivo: {HOTMART_FILE}")
    with open(HOTMART_FILE, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            total_hotmart += 1

            email = normalize_email(row.get("Email do(a) Comprador(a)", ""))
            if not email:
                skipped_no_email += 1
                continue
            if email in seen_emails:
                skipped_duplicate += 1
                continue
            seen_emails.add(email)

            first_name, last_name = normalize_name_parts(row.get("Comprador(a)", ""))
            phone = normalize_phone(row.get("Telefone", ""))
            zip_code = normalize_zip(row.get("Código postal", ""))

            rows_out.append([email, first_name, last_name, phone, zip_code, "BR"])

    # --- TMB ---
    print(f"Lendo arquivo: {TMB_FILE}")
    with open(TMB_FILE, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            total_tmb += 1

            status = row.get("Status Pedido", "")
            if status in TMB_STATUS_EXCLUIR:
                skipped_tmb_cancelado += 1
                continue

            email = normalize_email(row.get("E-mail do Cliente", ""))
            if not email:
                skipped_no_email += 1
                continue
            if email in seen_emails:
                skipped_duplicate += 1
                continue
            seen_emails.add(email)

            first_name, last_name = normalize_name_parts(row.get("Nome do Cliente", ""))
            phone = normalize_phone(row.get("Telefone do Cliente", ""))
            zip_code = normalize_zip(row.get("CEP", ""))

            rows_out.append([email, first_name, last_name, phone, zip_code, "BR"])

    # --- Escreve saída ---
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Email", "First Name", "Last Name", "Phone", "Zip", "Country"])
        writer.writerows(rows_out)

    print("\nArquivo gerado com sucesso!")
    print(f"   Registros Hotmart lidos:     {total_hotmart:,}")
    print(f"   Registros TMB lidos:         {total_tmb:,}")
    print(f"   TMB cancelados ignorados:    {skipped_tmb_cancelado:,}")
    print(f"   Ignorados (sem email):       {skipped_no_email:,}")
    print(f"   Ignorados (duplicados):      {skipped_duplicate:,}")
    print(f"   Registros exportados:        {len(rows_out):,}")
    print(f"\nArquivo salvo em:\n   {OUTPUT_FILE}")


if __name__ == "__main__":
    main()