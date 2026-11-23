import os
import hashlib
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
    Encoding
)

load_dotenv()

creds = google.oauth2.credentials.Credentials(
    token=None,
    refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
    token_uri="https://oauth2.googleapis.com/token",
    client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    scopes=["https://www.googleapis.com/auth/adwords", "https://www.googleapis.com/auth/datamanager"]
)
creds.refresh(google.auth.transport.requests.Request())

user_list_client = UserListServiceClient(credentials=creds)
ingestion_client = IngestionServiceClient(credentials=creds)

accounts = ["6482320788", "1450466453", "8399986700"]

test_email = "teste_ingestao_bot@braboconcursos.com.br"
email_hash = hashlib.sha256(test_email.strip().lower().encode()).hexdigest()

print("=" * 70)
print("TESTANDO UPLOAD VIA DATA MANAGER API NAS 3 CONTAS")
print("=" * 70)

for cid in accounts:
    parent = f"accountTypes/GOOGLE_ADS/accounts/{cid}"
    try:
        pager = user_list_client.list_user_lists(parent=parent)
        first_list = None
        for item in pager:
            first_list = item
            break
        
        if not first_list:
            print(f"Conta {cid}: Nenhuma lista encontrada.")
            continue

        member = AudienceMember(
            user_data=UserData(
                user_identifiers=[
                    UserIdentifier(email_address=email_hash)
                ]
            )
        )
        destination = Destination(
            operating_account=ProductAccount(
                product=Product.GOOGLE_ADS,
                account_id=cid
            ),
            product_destination_id=first_list.id
        )
        consent = Consent(
            ad_user_data=ConsentStatus.CONSENT_GRANTED,
            ad_personalization=ConsentStatus.CONSENT_GRANTED
        )
        terms = TermsOfService(
            customer_match_terms_of_service_status=TermsOfServiceStatus.ACCEPTED
        )
        request = IngestAudienceMembersRequest(
            destinations=[destination],
            consent=consent,
            terms_of_service=terms,
            encoding=Encoding.HEX,
            audience_members=[member],
            validate_only=True
        )
        resp = ingestion_client.ingest_audience_members(request=request)
        print(f"[OK] Conta {cid}: SUCESSO! Ingestao aceita na lista '{first_list.display_name}' (ID: {first_list.id})")
    except Exception as e:
        print(f"[ERRO] Conta {cid}: {e}")

print("=" * 70)
