"""
Script utilitário para criar públicos e fazer upload de listas de leads/clientes
para o Google Ads via Data Manager API (sem travas de Developer Token).

Uso via linha de comando — SEMPRE em duas rodadas (criar e ingerir juntos = lista fica vazia):
1. Criar a lista (só cria; não sobe ninguém):
   python scripts-python/upload_lista_google_ads.py --account 6482320788 --csv caminho/para/leads.csv --name "[LISTA] Cadastrados PES-SET-26"

2. Horas depois (o que funcionou: ~1 dia), subir os contatos na lista criada:
   python scripts-python/upload_lista_google_ads.py --account 6482320788 --list-id 9474740534 --csv caminho/para/leads.csv

Cada lote grava o request_id em outputs/customer_match_requests.jsonl — conferir o status e o tamanho
da lista antes de apontar um grupo ativo para ela.
"""

import os
import sys
import json
import hashlib
import argparse
from datetime import datetime
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

import google.oauth2.credentials
import google.auth.transport.requests
from google.ads.datamanager_v1 import (
    UserListServiceClient,
    IngestionServiceClient,
    IngestAudienceMembersRequest,
    AudienceMember,
    UserData,
    UserIdentifier,
    Consent,
    ConsentStatus,
    Destination,
    ProductAccount,
    Product,
    TermsOfService,
    TermsOfServiceStatus,
    Encoding,
    UserList,
    IngestedUserListInfo,
    ContactIdInfo
)

# Carrega ambiente
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MCC_PADRAO = "9335944411"  # login_account das contas BV-26 (padroes.GOOGLE_MCC)
REQUEST_LOG = Path(__file__).parent.parent / "outputs" / "customer_match_requests.jsonl"


def get_authenticated_clients():
    """Gera os clientes autenticados do Data Manager API."""
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        scopes=[
            "https://www.googleapis.com/auth/adwords",
            "https://www.googleapis.com/auth/datamanager"
        ]
    )
    creds.refresh(google.auth.transport.requests.Request())
    
    user_list_client = UserListServiceClient(credentials=creds)
    ingestion_client = IngestionServiceClient(credentials=creds)
    return user_list_client, ingestion_client


def create_user_list(user_list_client, account_id: str, list_name: str, description: str = "") -> str:
    """Cria uma nova lista de clientes (Customer Match) e retorna o ID da lista."""
    parent = f"accountTypes/GOOGLE_ADS/accounts/{account_id.replace('-', '')}"
    UploadKeyType = IngestedUserListInfo._meta.fields["upload_key_types"].enum
    
    new_user_list = UserList(
        display_name=list_name,
        description=description or f"Criada automaticamente via Data Manager API",
        ingested_user_list_info=IngestedUserListInfo(
            upload_key_types=[UploadKeyType.CONTACT_ID],
            contact_id_info=ContactIdInfo()
        )
    )
    created = user_list_client.create_user_list(parent=parent, user_list=new_user_list)
    print(f"✅ Público criado no Google Ads: '{created.display_name}' (ID: {created.id})")
    return str(created.id)


def hash_text(text: str) -> str:
    """Normaliza e gera hash SHA-256."""
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()


def upload_members(ingestion_client, account_id: str, list_id: str, emails: list[str] = None, phones: list[str] = None, batch_size: int = 5000, login_account: "str | None" = None):
    """Envia os membros (e-mails e/ou telefones) para a lista de público no Google Ads.

    Se a conta operacional está sob uma MCC, `login_account` precisa ser o ID da MCC:
    sem ele o Data Manager aceita a ingestão mas NÃO popula a lista (fica em 0).
    """
    account_id = account_id.replace("-", "")
    login_account = login_account.replace("-", "") if login_account else None
    emails = emails or []
    phones = phones or []
    
    all_members = []
    
    # Processa e-mails
    for em in set(emails):
        if em and isinstance(em, str) and "@" in em:
            all_members.append(
                AudienceMember(
                    user_data=UserData(
                        user_identifiers=[
                            UserIdentifier(email_address=hash_text(em))
                        ]
                    )
                )
            )
            
    # Processa telefones
    for ph in set(phones):
        if ph and isinstance(ph, (str, int)):
            ph_str = str(ph).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if not ph_str.startswith("+"):
                if ph_str.startswith("55"):
                    ph_str = "+" + ph_str
                else:
                    ph_str = "+55" + ph_str
            all_members.append(
                AudienceMember(
                    user_data=UserData(
                        user_identifiers=[
                            UserIdentifier(phone_number=hash_text(ph_str))
                        ]
                    )
                )
            )

    total = len(all_members)
    print(f"📦 Total de identificadores formatados para envio: {total}")
    
    if total == 0:
        print("⚠️ Nenhum contato válido para enviar.")
        return

    dest_kwargs = dict(
        operating_account=ProductAccount(product=Product.GOOGLE_ADS, account_id=account_id),
        product_destination_id=str(list_id),
    )
    if login_account:
        dest_kwargs["login_account"] = ProductAccount(product=Product.GOOGLE_ADS, account_id=login_account)
        print(f"🔑 login_account (MCC): {login_account}")
    destination = Destination(**dest_kwargs)
    consent = Consent(
        ad_user_data=ConsentStatus.CONSENT_GRANTED,
        ad_personalization=ConsentStatus.CONSENT_GRANTED
    )
    terms = TermsOfService(
        customer_match_terms_of_service_status=TermsOfServiceStatus.ACCEPTED
    )

    # Envio em lotes
    for i in range(0, total, batch_size):
        batch = all_members[i:i + batch_size]
        request = IngestAudienceMembersRequest(
            destinations=[destination],
            consent=consent,
            terms_of_service=terms,
            encoding=Encoding.HEX,
            audience_members=batch,
            validate_only=False
        )
        resp = ingestion_client.ingest_audience_members(request=request)
        print(f"🚀 Lote {i // batch_size + 1}/{(total - 1) // batch_size + 1} ({len(batch)} registros) enviado! (Request ID: {resp.request_id})")
        # "Aceito" não é "entrou na lista": o request_id é o único jeito de conferir depois
        # (IngestionServiceClient.retrieve_request_status). Sem ele, a falha de 09/10/26 ficou sem diagnóstico.
        with open(REQUEST_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"quando": datetime.now().isoformat(timespec="seconds"), "conta": account_id,
                                "lista": str(list_id), "lote": i // batch_size + 1, "registros": len(batch),
                                "request_id": resp.request_id}) + "\n")

    print(f"\n📨 {total} registros aceitos pela Data Manager para a lista {list_id} — aceito NÃO é populado.")
    print(f"   Conferir o status pelo request_id (log em {REQUEST_LOG}) e o tamanho da lista em algumas horas.")


def main():
    parser = argparse.ArgumentParser(description="Upload de listas para Google Ads via Data Manager API")
    parser.add_argument("--account", required=True, help="ID da conta Google Ads (ex: 6482320788)")
    parser.add_argument("--name", help="Nome da nova lista a ser criada")
    parser.add_argument("--list-id", help="ID de uma lista já existente (se não for criar uma nova)")
    parser.add_argument("--csv", required=True, help="Caminho para arquivo CSV com contatos")
    parser.add_argument("--email-col", default="email", help="Nome da coluna de e-mail no CSV (padrão: email)")
    parser.add_argument("--phone-col", default="phone", help="Nome da coluna de telefone no CSV (padrão: phone)")
    parser.add_argument("--login-account", default=MCC_PADRAO, help=f"ID da MCC (login_account). Padrão {MCC_PADRAO}: sem ele o Data Manager aceita mas não popula a lista.")

    args = parser.parse_args()

    if not args.name and not args.list_id:
        print("ERRO: Informe --name para criar uma nova lista ou --list-id para usar uma existente.")
        sys.exit(1)

    # dtype=str: telefone/CEP vêm como número e o pandas os lê como float
    # (ex.: "+5511..." vira 5511....0), perdendo o "+" e caindo no filtro
    # isinstance(ph,(str,int)) do upload_members — o que descarta TODOS os telefones.
    df = pd.read_csv(args.csv, dtype=str)
    emails = df[args.email_col].dropna().tolist() if args.email_col in df.columns else []
    phones = df[args.phone_col].dropna().tolist() if args.phone_col in df.columns else []

    user_list_client, ingestion_client = get_authenticated_clients()

    list_id = args.list_id
    if not list_id:
        # Criar e ingerir no mesmo comando faz a Data Manager aceitar e DESCARTAR os membros
        # (25/09 e 09/10/26 — MUDANCAS_BV-26 item 249). Só cria; a ingestão vem depois, em outra rodada.
        list_id = create_user_list(user_list_client, args.account, args.name)
        print(f"\n⏸ Lista {list_id} criada e VAZIA de propósito. Espere algumas horas (o que funcionou: ~1 dia) e rode de novo com:")
        print(f"   --account {args.account} --list-id {list_id} --csv \"{args.csv}\"")
        return

    upload_members(ingestion_client, args.account, list_id, emails=emails, phones=phones, login_account=args.login_account)


if __name__ == "__main__":
    main()
