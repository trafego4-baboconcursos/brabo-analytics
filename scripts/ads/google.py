"""Operações no Google Ads (REST) e na Data Manager API com os padrões da casa embutidos.

Regras que este módulo garante sozinho (ver MANUAL_OPERACAO_ADS.md):
- erro de API vira exceção com o código e a explicação conhecida — o helper antigo de debug imprimia o erro e
  devolvia lista vazia, o que num relatório de verba vira "R$ 0" em silêncio;
- campanha VIDEO nunca é mutada (MUTATE_NOT_ALLOWED permanente) — levanta ManualObrigatorio antes de tentar;
- verba só em orçamento próprio (compartilhado já estourou 337,8% no PES-SET-26);
- status muda nos 3 níveis e é conferido;
- em Demand Gen (público agrupado) exclusão entra no resource Audience, nunca como user_list solto no grupo;
- Customer Match sobe com login_account = MCC e consentimento — sem isso aceita e não popula.

Uso típico:
    from scripts.ads.google import Google
    g = Google()
    g.conferir_campanha("6482320788", "24289502823")
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from scripts.ads import padroes as P

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _http(metodo: str, url: str, tentativas: int = 3, **kw) -> requests.Response:
    """Nova tentativa só para queda de conexão/timeout (a API às vezes fecha a conexão no meio de um lote).
    Erro de API (4xx/5xx com corpo) volta na hora para quem chamou — esse não se repete."""
    for n in range(1, tentativas + 1):
        try:
            return requests.request(metodo, url, **kw)
        except (requests.ConnectionError, requests.Timeout):
            if n == tentativas:
                raise
            time.sleep(5 * n)

ERROS_GOOGLE = {
    "MUTATE_NOT_ALLOWED": "campanha VIDEO — a API nunca muta (permanente, não é nível de acesso). Fazer na interface.",
    "CANNOT_ADD_AUDIENCE_SEGMENT_CRITERION_WHEN_AUDIENCE_GROUPED_IS_SET":
        "público agrupado: editar o resource Audience (adicionar_exclusao_grupo), não user_list solto no grupo",
    "ONE_AUDIENCE_ALLOWED_PER_AD_GROUP": "Demand Gen aceita 1 Audience por grupo — juntar os segmentos num Audience só",
    "OPERATION_NOT_PERMITTED_FOR_CONTEXT": "Demand Gen exige audienceSetting.useAudienceGrouped = true",
    "YOUTUBE_VIDEO_DURATION_NOT_DEFINED": "ID de live do YouTube como asset — usar vídeo gravado; a live vai no finalUrls",
    "PROHIBITED_FIELD_IN_SELECT_CLAUSE": "campo não selecionável em GAQL (ex.: user_list.rule_based_user_list inteiro)",
    "CUSTOMER_NOT_ALLOWLISTED_FOR_THIS_FEATURE": "Customer Match pela Google Ads API é bloqueado — usar a Data Manager",
    "REQUIRED": "campo obrigatório faltando — em DemandGenVideoResponsiveAd costuma ser ad.name",
    "FIELD_HAS_SUBFIELDS": "updateMask precisa do subcampo (ex.: exclusion_dimension.exclusions, não exclusion_dimension)",
}


class GoogleErro(RuntimeError):
    def __init__(self, contexto: str, corpo: dict | str):
        self.codigos: list[str] = []
        msg = str(corpo)[:600]
        if isinstance(corpo, dict):
            for det in corpo.get("error", {}).get("details", []):
                for e in det.get("errors", []):
                    self.codigos += [v for v in (e.get("errorCode") or {}).values()]
            msg = corpo.get("error", {}).get("message", msg)
        dicas = [ERROS_GOOGLE[c] for c in self.codigos if c in ERROS_GOOGLE]
        super().__init__(f"Google {contexto}: {', '.join(self.codigos) or msg}"
                         + "".join(f"\n  → {d}" for d in dicas))


class ManualObrigatorio(RuntimeError):
    """A operação pedida só existe na interface do Google Ads (campanha VIDEO)."""


class Google:
    def __init__(self, versao: str = P.GOOGLE_API_VERSAO):
        self.versao = versao
        self._token, self._expira = None, 0.0

    # ------------------------------------------------------------------ transporte
    def _headers(self) -> dict:
        if time.time() > self._expira:
            r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
                "grant_type": "refresh_token", "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
                "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"], "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"]})
            r.raise_for_status()
            self._token, self._expira = r.json()["access_token"], time.time() + 3000
        return {"Authorization": f"Bearer {self._token}", "developer-token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
                "login-customer-id": os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", P.GOOGLE_MCC).replace("-", "")}

    def _url(self, conta: str, sufixo: str) -> str:
        return f"https://googleads.googleapis.com/{self.versao}/customers/{conta}/{sufixo}"

    def buscar(self, conta: str, gaql: str) -> list[dict]:
        out, pagina = [], None
        while True:
            r = _http("POST", self._url(conta, "googleAds:search"), headers=self._headers(), timeout=90,
                              json={"query": gaql, **({"pageToken": pagina} if pagina else {})})
            if r.status_code != 200:
                raise GoogleErro(f"busca {conta}", r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)
            d = r.json()
            out += d.get("results", [])
            pagina = d.get("nextPageToken")
            if not pagina:
                return out

    def mutar(self, conta: str, recurso: str, operacoes: list[dict], validar: bool = False) -> list[dict]:
        """`recurso` = campaigns, adGroups, adGroupAds, campaignBudgets, audiences, userLists…
        `validar=True` confere o pedido sem gravar nada (bom para piloto)."""
        r = _http("POST", self._url(conta, f"{recurso}:mutate"), headers=self._headers(), timeout=120,
                          json={"operations": operacoes, "validateOnly": validar})
        if r.status_code != 200:
            raise GoogleErro(f"{recurso}:mutate {conta}", r.json())
        return r.json().get("results", [])

    # ------------------------------------------------------------------ consultas
    def campanhas(self, conta: str, contem: str = "") -> list[dict]:
        filtro = f"AND campaign.name LIKE '%{contem}%'" if contem else ""
        return [x["campaign"] | {"campaignBudget": x.get("campaignBudget", {})} for x in self.buscar(conta, f"""
            SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type,
                   campaign.start_date, campaign.end_date, campaign_budget.amount_micros,
                   campaign_budget.explicitly_shared, campaign_budget.reference_count, campaign_budget.resource_name
            FROM campaign WHERE campaign.status != 'REMOVED' {filtro}""")]

    def _campanha(self, conta: str, campanha_id: str) -> dict:
        r = self.buscar(conta, f"""SELECT campaign.name, campaign.advertising_channel_type, campaign.status,
            campaign.end_date, campaign.bidding_strategy_type, campaign.tracking_url_template,
            campaign.url_custom_parameters, campaign.audience_setting.use_audience_grouped,
            campaign_budget.resource_name, campaign_budget.amount_micros, campaign_budget.explicitly_shared,
            campaign_budget.reference_count FROM campaign WHERE campaign.id = {campanha_id}""")
        if not r:
            raise GoogleErro(f"campanha {campanha_id}", "não encontrada")
        return r[0]

    def _nao_video(self, conta: str, campanha_id: str) -> dict:
        c = self._campanha(conta, campanha_id)
        if c["campaign"].get("advertisingChannelType") == "VIDEO":
            raise ManualObrigatorio(f"{c['campaign']['name']} é VIDEO — a API não muta; fazer na interface")
        return c

    # ------------------------------------------------------------------ status, verba, datas
    def definir_fim(self, conta: str, campanha_id: str, data: str) -> None:
        """`data` = 'AAAA-MM-DD'. No Google a campanha para no fim desse dia."""
        self._nao_video(conta, campanha_id)
        rn = f"customers/{conta}/campaigns/{campanha_id}"
        self.mutar(conta, "campaigns", [{"update": {"resourceName": rn, "endDate": data}, "updateMask": "end_date"}])
        if self._campanha(conta, campanha_id)["campaign"].get("endDate") != data:
            raise RuntimeError(f"{campanha_id}: end_date não aplicou")

    def definir_status(self, conta: str, campanha_id: str, status: str) -> dict:
        """ENABLED/PAUSED na campanha, nos grupos e nos anúncios (status não cascateia)."""
        assert status in ("ENABLED", "PAUSED")
        self._nao_video(conta, campanha_id)
        grupos = self.buscar(conta, f"SELECT ad_group.resource_name FROM ad_group WHERE campaign.id = {campanha_id} "
                                    "AND ad_group.status != 'REMOVED'")
        ads = self.buscar(conta, f"SELECT ad_group_ad.resource_name FROM ad_group_ad WHERE campaign.id = {campanha_id} "
                                 "AND ad_group_ad.status != 'REMOVED'")
        self.mutar(conta, "campaigns", [{"update": {"resourceName": f"customers/{conta}/campaigns/{campanha_id}",
                                                    "status": status}, "updateMask": "status"}])
        if grupos:
            self.mutar(conta, "adGroups", [{"update": {"resourceName": g["adGroup"]["resourceName"], "status": status},
                                            "updateMask": "status"} for g in grupos])
        if ads:
            self.mutar(conta, "adGroupAds", [{"update": {"resourceName": a["adGroupAd"]["resourceName"], "status": status},
                                              "updateMask": "status"} for a in ads])
        return {"grupos": len(grupos), "anuncios": len(ads)}

    def definir_verba_diaria(self, conta: str, campanha_id: str, reais: float) -> None:
        c = self._nao_video(conta, campanha_id)
        b = c["campaignBudget"]
        if b.get("explicitlyShared") or int(b.get("referenceCount", 1)) > 1:
            raise RuntimeError(f"{campanha_id}: orçamento compartilhado — separar antes (regra: orçamento próprio)")
        if (c["campaign"].get("advertisingChannelType") == "DEMAND_GEN"
                and c["campaign"].get("biddingStrategyType") == "TARGET_CPA" and reais < P.DEMAND_GEN_TCPA_MINIMO):
            raise ValueError(f"Demand Gen com tCPA: mínimo R$ {P.DEMAND_GEN_TCPA_MINIMO}/dia")
        self.mutar(conta, "campaignBudgets", [{"update": {"resourceName": b["resourceName"],
                                                           "amountMicros": str(round(reais * 1_000_000))},
                                                "updateMask": "amount_micros"}])

    # ------------------------------------------------------------------ públicos
    def corrigir_duracao_listas(self, conta: str, contem: str) -> list[str]:
        """Listas de site com duração 0 (a pessoa sai na hora) → P.LISTA_SITE_DURACAO dias."""
        zeradas = [x["userList"]["id"] for x in self.buscar(conta, f"""SELECT user_list.id, user_list.membership_life_span
            FROM user_list WHERE user_list.type = 'RULE_BASED' AND user_list.name LIKE '%{contem}%'""")
                   if str(x["userList"].get("membershipLifeSpan", "")) == "0"]
        if zeradas:
            self.mutar(conta, "userLists", [{"update": {"resourceName": f"customers/{conta}/userLists/{i}",
                                                         "membershipLifeSpan": str(P.LISTA_SITE_DURACAO)},
                                              "updateMask": "membership_life_span"} for i in zeradas])
        return zeradas

    def adicionar_exclusao_grupo(self, conta: str, grupo_id: str, user_list_id: str, validar: bool = False) -> str:
        """Demand Gen (público agrupado): acrescenta a lista à exclusão do Audience do grupo.
        ATENÇÃO: o Audience pode ser usado por mais de um grupo — a mudança vale para todos eles.
        Use validar=True no piloto. Retorna o resource do Audience alterado."""
        crit = self.buscar(conta, f"""SELECT ad_group_criterion.audience.audience FROM ad_group_criterion
            WHERE ad_group.id = {grupo_id} AND ad_group_criterion.type = 'AUDIENCE'""")
        if not crit:
            raise RuntimeError(f"grupo {grupo_id} sem Audience (não é público agrupado?)")
        aud = crit[0]["adGroupCriterion"]["audience"]["audience"]
        atual = self.buscar(conta, f"SELECT audience.exclusion_dimension FROM audience WHERE audience.resource_name = '{aud}'")
        exclusoes = ((atual[0]["audience"].get("exclusionDimension") or {}).get("exclusions") or []) if atual else []
        alvo = f"customers/{conta}/userLists/{user_list_id}"
        if any((e.get("userList") or {}).get("userList") == alvo for e in exclusoes):
            return aud
        exclusoes = exclusoes + [{"userList": {"userList": alvo}}]
        self.mutar(conta, "audiences", [{"update": {"resourceName": aud, "exclusionDimension": {"exclusions": exclusoes}},
                                         "updateMask": "exclusion_dimension.exclusions"}], validar=validar)
        return aud

    def definir_regiao_grupos(self, conta: str, campanha_id: str, geo: str = P.GEO_GOOGLE_BRASIL,
                              idiomas: list[str] | None = None, validar: bool = False) -> int:
        """Região e idiomas em cada grupo de uma campanha com público agrupado (Demand Gen), onde a campanha
        não aceita LOCATION/LANGUAGE. Só cria o que falta. Retorna quantos critérios criou."""
        idiomas = P.IDIOMAS_GOOGLE if idiomas is None else idiomas
        self._nao_video(conta, campanha_id)
        grupos = [x["adGroup"]["resourceName"] for x in self.buscar(conta, f"""SELECT ad_group.resource_name
            FROM ad_group WHERE campaign.id = {campanha_id} AND ad_group.status != 'REMOVED'""")]
        existentes = {(x["adGroup"]["resourceName"], (x["adGroupCriterion"].get("location") or {}).get("geoTargetConstant")
                       or (x["adGroupCriterion"].get("language") or {}).get("languageConstant"))
                      for x in self.buscar(conta, f"""SELECT ad_group.resource_name, ad_group_criterion.location.geo_target_constant,
                          ad_group_criterion.language.language_constant FROM ad_group_criterion
                          WHERE campaign.id = {campanha_id} AND ad_group_criterion.type IN ('LOCATION', 'LANGUAGE')""")}
        ops = []
        for gr in grupos:
            if (gr, geo) not in existentes:
                ops.append({"create": {"adGroup": gr, "location": {"geoTargetConstant": geo}}})
            ops += [{"create": {"adGroup": gr, "language": {"languageConstant": i}}} for i in idiomas if (gr, i) not in existentes]
        if ops:
            self.mutar(conta, "adGroupCriteria", ops, validar=validar)
        return len(ops)

    def customer_match(self, conta: str, lista_id: str, pessoas: list[dict], remover: bool = False) -> str:
        """Adiciona (ou remove) pessoas de uma lista de Customer Match pela Data Manager API, com
        login_account = MCC (sem ele aceita e não popula). A conta precisa estar com consentimento
        "Consentido" (Configurações de consentimento → Dados importados e enviados). Retorna o request id."""
        import google.auth.transport.requests
        import google.oauth2.credentials
        from google.ads import datamanager_v1 as dm

        creds = google.oauth2.credentials.Credentials(
            token=None, refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GOOGLE_ADS_CLIENT_ID"], client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
            scopes=["https://www.googleapis.com/auth/adwords", "https://www.googleapis.com/auth/datamanager"])
        creds.refresh(google.auth.transport.requests.Request())
        cliente = dm.IngestionServiceClient(credentials=creds)
        membros = []
        for ident in identificadores_google(pessoas):
            membros.append(dm.AudienceMember(user_data=dm.UserData(user_identifiers=[dm.UserIdentifier(**ident)])))
        destino = dm.Destination(operating_account=dm.ProductAccount(product=dm.Product.GOOGLE_ADS, account_id=conta),
                                 login_account=dm.ProductAccount(product=dm.Product.GOOGLE_ADS, account_id=P.GOOGLE_MCC),
                                 product_destination_id=str(lista_id))
        ultimo = ""
        for i in range(0, len(membros), 5000):
            lote = membros[i:i + 5000]
            if remover:
                resp = cliente.remove_audience_members(request=dm.RemoveAudienceMembersRequest(
                    destinations=[destino], encoding=dm.Encoding.HEX, audience_members=lote))
            else:
                resp = cliente.ingest_audience_members(request=dm.IngestAudienceMembersRequest(
                    destinations=[destino], encoding=dm.Encoding.HEX, audience_members=lote,
                    consent=dm.Consent(ad_user_data=dm.ConsentStatus.CONSENT_GRANTED,
                                       ad_personalization=dm.ConsentStatus.CONSENT_GRANTED),
                    terms_of_service=dm.TermsOfService(
                        customer_match_terms_of_service_status=dm.TermsOfServiceStatus.ACCEPTED)))
            ultimo = resp.request_id
        return ultimo

    # ------------------------------------------------------------------ conferência
    def conferir_campanha(self, conta: str, campanha_id: str) -> list[str]:
        """Checklist: orçamento próprio, data de fim, tracking template, parâmetros personalizados nos 3
        níveis e (público agrupado) região/idioma no grupo. Campanha VIDEO: só lê, avisa que é manual."""
        c = self._campanha(conta, campanha_id)
        camp, b, out = c["campaign"], c["campaignBudget"], []
        nome = camp["name"]
        # VIDEO não é problema — só não dá para corrigir por API. conferir.py mostra como aviso.
        if b.get("explicitlyShared") or int(b.get("referenceCount", 1)) > 1:
            out.append(f"{nome}: orçamento compartilhado")
        if not camp.get("endDate") or camp["endDate"].startswith("2037"):
            out.append(f"{nome}: sem data de fim ({camp.get('endDate') or 'vazia'})")
        if not camp.get("trackingUrlTemplate"):
            out.append(f"{nome}: sem tracking_url_template")
        params = {p["key"]: p.get("value") for p in camp.get("urlCustomParameters", [])}
        if params.get(P.GOOGLE_PARAMETROS["campanha"]) is None:
            out.append(f"{nome}: sem parâmetro personalizado campaignname")
        grupos = self.buscar(conta, f"""SELECT ad_group.id, ad_group.name, ad_group.url_custom_parameters
            FROM ad_group WHERE campaign.id = {campanha_id} AND ad_group.status != 'REMOVED'""")
        for g in grupos:
            gp = {p["key"] for p in g["adGroup"].get("urlCustomParameters", [])}
            if P.GOOGLE_PARAMETROS["grupo"] not in gp:
                out.append(f"{nome} / {g['adGroup']['name']}: sem parâmetro adgroupname")
        ads = self.buscar(conta, f"""SELECT ad_group_ad.ad.name, ad_group_ad.ad.url_custom_parameters
            FROM ad_group_ad WHERE campaign.id = {campanha_id} AND ad_group_ad.status = 'ENABLED'""")
        sem_adname = [a["adGroupAd"]["ad"].get("name") for a in ads
                      if P.GOOGLE_PARAMETROS["anuncio"] not in {p["key"] for p in a["adGroupAd"]["ad"].get("urlCustomParameters", [])}]
        if sem_adname:
            out.append(f"{nome}: {len(sem_adname)} anúncio(s) sem parâmetro adname (ex.: {sem_adname[0]})")
        # Região: na campanha (VIDEO, Search) ou em cada grupo (Demand Gen com público agrupado, onde a
        # campanha não aceita LOCATION). Sem nenhuma das duas, a campanha roda em qualquer país.
        geo_campanha = self.buscar(conta, f"""SELECT campaign_criterion.criterion_id FROM campaign_criterion
            WHERE campaign.id = {campanha_id} AND campaign_criterion.type = 'LOCATION'""")
        if not geo_campanha:
            com_geo = {x["adGroup"]["id"] for x in self.buscar(conta, f"""SELECT ad_group.id FROM ad_group_criterion
                WHERE campaign.id = {campanha_id} AND ad_group_criterion.type = 'LOCATION'""")}
            faltam = [g["adGroup"]["name"] for g in grupos if g["adGroup"]["id"] not in com_geo]
            if faltam:
                out.append(f"{nome}: sem região (nem na campanha nem em {len(faltam)} grupo(s)) — roda em qualquer país")
        return out


# ---------------------------------------------------------------------------- funções puras (testadas)
def _sha(v: str) -> str:
    return hashlib.sha256(v.strip().lower().encode("utf-8")).hexdigest()


def identificadores_google(pessoas: list[dict]) -> list[dict]:
    """E-mail e telefone viram identificadores separados, com hash (formato da Data Manager)."""
    from scripts.ads.meta import telefone_e164
    out = []
    for p in pessoas:
        email = (p.get("email") or "").strip().lower()
        if "@" in email:
            out.append({"email_address": _sha(email)})
        tel = telefone_e164(p.get("phone"))
        if len(tel) >= 12:
            out.append({"phone_number": _sha("+" + tel)})
    return out
