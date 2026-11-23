import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
load_dotenv(Path(__file__).parent.parent.parent / ".env")

API_VERSION = "v22"

def get_access_token():
    import google.oauth2.credentials
    import google.auth.transport.requests
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token

def query_google_ads(customer_id: str, query: str):
    token = get_access_token()
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "9335944411").replace("-", "")
    dev_token = os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"]
    
    headers = {
        "Authorization": f"Bearer {token}",
        "developer-token": dev_token,
        "Content-Type": "application/json",
        "login-customer-id": login_customer_id
    }
    
    url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{customer_id}/googleAds:search"
    results = []
    page_token = None
    
    while True:
        payload = {"query": query}
        if page_token:
            payload["pageToken"] = page_token
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                results.extend(data.get("results", []))
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"Erro HTTP na conta {customer_id}: {e.code} - {err_body}", flush=True)
            break
        except Exception as e:
            print(f"Erro geral: {e}", flush=True)
            break
    return results

def main():
    cid = "6482320788"
    c_id = 24281955281
    
    print("="*90)
    print("RAIO-X FORENSE DA CAMPANHA 24281955281 (ALUNOS BV-26)")
    print("="*90)

    # 1. Configurações completas da Campanha
    q_camp = f"""
    SELECT
      campaign.id,
      campaign.name,
      campaign.status,
      campaign.serving_status,
      campaign.primary_status,
      campaign.advertising_channel_type,
      campaign.advertising_channel_sub_type,
      campaign.frequency_caps,
      campaign.video_brand_safety_suitability,
      campaign.network_settings.target_google_search,
      campaign.network_settings.target_search_network,
      campaign.network_settings.target_content_network,
      campaign.network_settings.target_partner_search_network,
      campaign.network_settings.target_youtube,
      campaign.bidding_strategy_type,
      campaign.accessible_bidding_strategy
    FROM campaign
    WHERE campaign.id = {c_id}
    """
    camps = query_google_ads(cid, q_camp)
    print("\n[1] CONFIGURAÇÃO DA CAMPANHA:")
    if camps:
        c = camps[0].get("campaign", {})
        print(f"Nome: {c.get('name')}")
        print(f"Tipo: {c.get('advertisingChannelType')} | SubTipo: {c.get('advertisingChannelSubType')}")
        print(f"Status: {c.get('status')} | Serv: {c.get('servingStatus')} | Primary: {c.get('primaryStatus')}")
        print(f"Bidding Strategy: {c.get('biddingStrategyType')}")
        print(f"Network Settings: {c.get('networkSettings')}")
        print(f"Frequency Caps: {c.get('frequencyCaps')}")
        print(f"Brand Safety: {c.get('videoBrandSafetySuitability')}")

    # 2. Configurações do Ad Group (Targeting Setting / Restrictions)
    q_ag = f"""
    SELECT
      ad_group.id,
      ad_group.name,
      ad_group.status,
      ad_group.type,
      ad_group.targeting_setting.target_restrictions
    FROM ad_group
    WHERE campaign.id = {c_id}
    """
    ags = query_google_ads(cid, q_ag)
    print("\n[2] TARGETING RESTRICTIONS NOS AD GROUPS:")
    for ag in ags:
        ag_o = ag.get("adGroup", {})
        ag_id = ag_o.get("id")
        t_rest = ag_o.get("targetingSetting", {}).get("targetRestrictions", [])
        print(f"Grupo [{ag_id}] {ag_o.get('name')} (Tipo: {ag_o.get('type')}):")
        for tr in t_rest:
            print(f"   - Dimensão: {tr.get('targetingDimension')} | Bid Only: {tr.get('bidOnly')}")

    # 3. Exclusões de Conteúdo e Tópicos na Campanha
    q_neg = f"""
    SELECT
      campaign_criterion.criterion_id,
      campaign_criterion.display_name,
      campaign_criterion.type,
      campaign_criterion.negative
    FROM campaign_criterion
    WHERE campaign.id = {c_id} AND campaign_criterion.negative = true
    """
    negs = query_google_ads(cid, q_neg)
    print(f"\n[3] EXCLUSÕES A NÍVEL DE CAMPANHA ({len(negs)}):")
    for n in negs:
        cc = n.get("campaignCriterion", {})
        print(f"   - {cc.get('type')}: {cc.get('displayName') or cc.get('criterionId')}")

    # 4. Detalhes dos Vídeos/Anúncios nos Ad Groups
    q_ads = f"""
    SELECT
      ad_group_ad.ad.id,
      ad_group_ad.ad.name,
      ad_group_ad.ad.type,
      ad_group_ad.ad.video_responsive_ad.videos,
      ad_group_ad.ad.video_responsive_ad.call_to_actions,
      ad_group_ad.ad.video_responsive_ad.headlines,
      ad_group_ad.ad.video_responsive_ad.long_headlines,
      ad_group_ad.ad.video_responsive_ad.descriptions,
      ad_group_ad.ad.final_urls
    FROM ad_group_ad
    WHERE campaign.id = {c_id} AND ad_group_ad.status = 'ENABLED'
    """
    ads = query_google_ads(cid, q_ads)
    print(f"\n[4] ANÚNCIOS ATIVOS ({len(ads)}):")
    for a in ads:
        ad_o = a.get("adGroupAd", {}).get("ad", {})
        vra = ad_o.get("videoResponsiveAd", {})
        print(f"Ad [{ad_o.get('id')}]: {ad_o.get('name')}")
        print(f"   Final URLs: {ad_o.get('finalUrls')}")
        print(f"   Videos: {vra.get('videos')}")
        print(f"   Headlines: {vra.get('headlines')}")
        print(f"   Descriptions: {vra.get('descriptions')}")

if __name__ == "__main__":
    main()
