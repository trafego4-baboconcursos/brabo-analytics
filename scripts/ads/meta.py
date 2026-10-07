"""Operações no Meta (Marketing API) com os padrões da casa embutidos.

Regras que este módulo garante sozinho (ver MANUAL_OPERACAO_ADS.md):
- erro de API vira exceção com o código, o subcode e a explicação conhecida — nada de seguir com resultado vazio;
- todo campo dict/lista do payload é serializado com json.dumps (erro genérico 1815166 quando não é);
- alterar targeting = ler inteiro, mudar, devolver inteiro e reler depois de alguns segundos;
- anúncio novo sai sempre com o pixel no tracking_specs, mesmo reaproveitando creative_id;
- criativo novo sai sempre com a UTM padrão em url_tags;
- status e data de fim mudam nos 3 níveis (campanha, conjunto, anúncio) e são conferidos.

Uso típico:
    from scripts.ads.meta import Meta
    m = Meta()
    m.adicionar_exclusao("120248104350210014", "120253693257560754", "[Site] Cadastrados ...")
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable

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

# Subcodes que já custaram tempo — a exceção traz a explicação junto. Tabela completa no manual.
ERROS_META = {
    1815166: "payload com dict/lista sem json.dumps (object_story_spec, asset_feed_spec, targeting...)",
    1359207: "público de outra conta não compartilhado — compartilhar_publico() antes",
    1870227: "targeting sem targeting_automation.advantage_audience",
    3858634: "geo BR sem regional_regulated_categories/identities (padroes.REGULACAO_BR)",
    1885650: f"verba abaixo do mínimo do CBO (~R$ {P.META_CBO_MINIMO:.0f}/dia)",
    1885154: "ad set de engajamento sem destination_type=ON_VIDEO / promoted_object",
    1487664: "vídeo feed+story: use call_to_action_types (plural) + ad_formats AUTOMATIC_FORMAT",
    1487390: "criativo por posicionamento: falta optimization_type PLACEMENT ou labels em bodies/link_urls",
    1487057: "start_time de ad set que já começou não muda — recriar o ad set",
    1634011: "chave do pixel no tracking_specs é fb_pixel (com underscore)",
    1815045: "conta sem acesso ao pixel (Felipe Nova não acessa o 608 — usar o 990)",
    1815573: "campo do criativo é imutável — perguntar ao usuário antes de recriar",
    1713216: "vídeo sem post de Página — usar o vídeo publicado (page token) no público de engajamento",
    1870049: "público de % de vídeo usa o formato de regra antigo (lista plana)",
    1870053: "público WEBSITE não leva subtype — a rule com event_sources já define",
}


class MetaErro(RuntimeError):
    def __init__(self, caminho: str, erro: dict):
        self.code = erro.get("code")
        self.subcode = erro.get("error_subcode")
        self.mensagem = erro.get("error_user_msg") or erro.get("message")
        dica = ERROS_META.get(self.subcode, "")
        super().__init__(f"Meta {caminho}: code={self.code} subcode={self.subcode} — {self.mensagem}"
                         + (f"\n  → {dica}" if dica else ""))


def _serializar(dados: dict) -> dict:
    """Form-encoded do requests faz str(dict) (aspas simples) — serializa tudo que não é escalar."""
    return {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            for k, v in dados.items() if v is not None}


class Meta:
    def __init__(self, token: str | None = None, versao: str = P.GRAPH_VERSAO):
        self.token = token or os.environ["META_ACCESS_TOKEN"]
        self.base = f"https://graph.facebook.com/{versao}"

    # ------------------------------------------------------------------ transporte
    def get(self, caminho: str, **params) -> dict:
        r = _http("GET", f"{self.base}/{caminho.lstrip('/')}",
                         params={"access_token": self.token, **_serializar(params)}, timeout=90).json()
        if "error" in r:
            raise MetaErro(caminho, r["error"])
        return r

    def listar(self, caminho: str, **params) -> list[dict]:
        params.setdefault("limit", 100)
        url, qs, out = f"{self.base}/{caminho.lstrip('/')}", {"access_token": self.token, **_serializar(params)}, []
        while url:
            r = _http("GET", url, params=qs, timeout=90).json()
            qs = None
            if "error" in r:
                raise MetaErro(caminho, r["error"])
            out += r.get("data", [])
            url = r.get("paging", {}).get("next")
        return out

    def post(self, caminho: str, **dados) -> dict:
        r = _http("POST", f"{self.base}/{caminho.lstrip('/')}",
                          data={"access_token": self.token, **_serializar(dados)}, timeout=180).json()
        if "error" in r:
            raise MetaErro(caminho, r["error"])
        return r

    # ------------------------------------------------------------------ consultas
    def campanhas(self, conta: str, *contem: str, campos: str = "id,name,effective_status,daily_budget,stop_time") -> list[dict]:
        filtro = [{"field": "name", "operator": "CONTAIN", "value": c} for c in contem]
        return self.listar(f"{conta}/campaigns", fields=campos, filtering=filtro)

    def adsets(self, campanha_id: str, campos: str = "id,name,effective_status,status,end_time,targeting") -> list[dict]:
        return self.listar(f"{campanha_id}/adsets", fields=campos)

    def anuncios(self, pai_id: str, campos: str = "id,name,status,effective_status,tracking_specs,"
                                                 "creative{id,url_tags,object_story_spec,asset_feed_spec}") -> list[dict]:
        return self.listar(f"{pai_id}/ads", fields=campos)

    # ------------------------------------------------------------------ targeting
    def alterar_targeting(self, adset_id: str, mudanca: Callable[[dict], None], esperar: float = 8) -> dict:
        """Lê o targeting inteiro, aplica `mudanca` (edita o dict no lugar), devolve inteiro e confere.

        Update de targeting SUBSTITUI o objeto todo — nunca mandar só o campo novo. A releitura espera
        alguns segundos: logo após o POST o Meta devolve o valor antigo. Retorna o targeting relido.
        """
        antes = self.get(adset_id, fields="targeting")["targeting"]
        novo = json.loads(json.dumps(antes))
        mudanca(novo)
        self.post(adset_id, targeting=novo)
        time.sleep(esperar)
        depois = self.get(adset_id, fields="targeting")["targeting"]
        # O Meta acrescenta targeting_relaxation_types ao gravar — não é perda de dado.
        ignorar = {"targeting_relaxation_types"}
        faltando = [k for k in novo if k not in ignorar and k not in depois]
        if faltando:
            raise RuntimeError(f"{adset_id}: targeting relido sem {faltando} — conferir antes de seguir")
        return depois

    def adicionar_exclusao(self, adset_id: str, audience_id: str, nome: str = "") -> bool:
        """Acrescenta um público à exclusão. Retorna False se já estava."""
        atual = self.get(adset_id, fields="targeting")["targeting"].get("excluded_custom_audiences", [])
        if any(a["id"] == audience_id for a in atual):
            return False

        def _mudar(t: dict) -> None:
            t.setdefault("excluded_custom_audiences", []).append({"id": audience_id, "name": nome})

        depois = self.alterar_targeting(adset_id, _mudar)
        if audience_id not in [a["id"] for a in depois.get("excluded_custom_audiences", [])]:
            raise RuntimeError(f"{adset_id}: exclusão {audience_id} não aparece na releitura")
        return True

    # ------------------------------------------------------------------ status, verba, datas
    def definir_status(self, campanha_id: str, status: str) -> dict:
        """ACTIVE/PAUSED na campanha, em todos os conjuntos e em todos os anúncios (status não cascateia)."""
        assert status in ("ACTIVE", "PAUSED")
        self.post(campanha_id, status=status)
        adsets = self.listar(f"{campanha_id}/adsets", fields="id")
        for a in adsets:
            self.post(a["id"], status=status)
        ads = self.listar(f"{campanha_id}/ads", fields="id")
        for a in ads:
            self.post(a["id"], status=status)
        time.sleep(5)
        errados = [x["id"] for x in self.listar(f"{campanha_id}/adsets", fields="id,status") + self.listar(
            f"{campanha_id}/ads", fields="id,status") if x["status"] != status]
        if self.get(campanha_id, fields="status")["status"] != status or errados:
            raise RuntimeError(f"{campanha_id}: status {status} não aplicou em {errados or 'campanha'}")
        return {"conjuntos": len(adsets), "anuncios": len(ads)}

    def definir_verba_diaria(self, campanha_id: str, reais: float) -> None:
        """CBO diário da campanha. Abaixo do mínimo o Meta recusa — a exceção explica."""
        if reais < P.META_CBO_MINIMO:
            raise ValueError(f"R$ {reais:.2f}/dia está abaixo do mínimo do CBO (~R$ {P.META_CBO_MINIMO:.0f})")
        self.post(campanha_id, daily_budget=str(round(reais * 100)))
        time.sleep(4)
        lido = int(self.get(campanha_id, fields="daily_budget")["daily_budget"]) / 100
        if abs(lido - reais) > 0.02:
            raise RuntimeError(f"{campanha_id}: verba lida R$ {lido} ≠ R$ {reais}")

    def definir_fim(self, campanha_id: str, fim_iso: str) -> int:
        """Fim da campanha (stop_time) e de todos os conjuntos (end_time) — o que vale para entrega é o do
        conjunto. `fim_iso` no formato 2026-10-10T18:00:00-0300. Retorna quantos conjuntos mudaram."""
        self.post(campanha_id, stop_time=fim_iso)
        adsets = self.listar(f"{campanha_id}/adsets", fields="id")
        for a in adsets:
            self.post(a["id"], end_time=fim_iso)
        time.sleep(5)
        alvo = fim_iso[:16]
        errados = [a["id"] for a in self.listar(f"{campanha_id}/adsets", fields="id,end_time")
                   if not (a.get("end_time") or "").startswith(alvo)]
        if errados:
            raise RuntimeError(f"{campanha_id}: end_time não aplicou em {errados}")
        return len(adsets)

    # ------------------------------------------------------------------ públicos
    def compartilhar_publico(self, audience_id: str, contas: Iterable[str]) -> None:
        """Público de outra conta não é compartilhado automaticamente (subcode 1359207)."""
        ids = [c.replace("act_", "") for c in contas]
        self.post(f"{audience_id}/adaccounts", adaccounts=ids)

    def substituir_membros(self, audience_id: str, pessoas: list[dict]) -> int:
        """Troca TODOS os membros de um público de lista (usersreplace). `pessoas`: dicts com
        email, phone, first_name, last_name (o que tiver). Hash SHA-256 feito aqui. Retorna recebidos."""
        linhas = [linha_hash(p) for p in pessoas]
        sessao = random.randint(10**9, 10**10)
        recebidos = 0
        lotes = [linhas[i:i + 10000] for i in range(0, len(linhas), 10000)] or [[]]
        for n, lote in enumerate(lotes, 1):
            r = self.post(f"{audience_id}/usersreplace",
                          session={"session_id": sessao, "batch_seq": n, "last_batch_flag": n == len(lotes),
                                   "estimated_num_total": len(linhas)},
                          payload={"schema": ["EMAIL", "PHONE", "FN", "LN", "COUNTRY"], "data": lote})
            if r.get("num_invalid_entries"):
                raise RuntimeError(f"{audience_id}: {r['num_invalid_entries']} inválidos — {r.get('invalid_entry_samples')}")
            recebidos = r.get("num_received", recebidos)  # vem acumulado, não somar entre lotes
        return recebidos

    # ------------------------------------------------------------------ criação
    def criar_criativo(self, conta: str, nome: str, expert: str, *, asset_feed_spec: dict | None = None,
                       object_story_spec: dict | None = None) -> str:
        """Criativo com página/Instagram do expert e a UTM padrão em url_tags (nunca no link)."""
        e = P.META_EXPERTS[expert]
        oss = {"page_id": e["page_id"], "instagram_user_id": e["instagram_user_id"], **(object_story_spec or {})}
        for link in links_do_criativo({"object_story_spec": oss, "asset_feed_spec": asset_feed_spec or {}}):
            if "utm_" in link:
                raise ValueError(f"link com UTM colada ({link}) — a UTM vai em url_tags")
        r = self.post(f"{conta}/adcreatives", name=nome, object_story_spec=oss,
                      asset_feed_spec=asset_feed_spec, url_tags=P.UTM_META)
        return r["id"]

    def criar_anuncio(self, conta: str, adset_id: str, nome: str, creative_id: str, expert: str,
                      status: str = "PAUSED") -> str:
        """Anúncio com o pixel do expert no tracking_specs — obrigatório mesmo reaproveitando creative_id."""
        pixel = P.META_EXPERTS[expert]["pixel_id"]
        r = self.post(f"{conta}/ads", name=nome, adset_id=adset_id, status=status,
                      creative={"creative_id": creative_id},
                      tracking_specs=[{"action.type": ["offsite_conversion"], "fb_pixel": [pixel]}])
        return r["id"]

    def garantir_pixel(self, ad_id: str, pixel_id: str) -> bool:
        """Põe o pixel no tracking_specs de um anúncio já criado (mantém os specs que já existem).
        Retorna False se já estava. Caso típico: anúncio replicado reaproveitando creative_id."""
        specs = self.get(ad_id, fields="tracking_specs").get("tracking_specs", [])
        if any(pixel_id in [str(x) for x in (s_.get("fb_pixel") or [])] for s_ in specs):
            return False
        self.post(ad_id, tracking_specs=specs + [{"action.type": ["offsite_conversion"], "fb_pixel": [pixel_id]}])
        time.sleep(3)
        lidos = self.get(ad_id, fields="tracking_specs").get("tracking_specs", [])
        if not any(pixel_id in [str(x) for x in (s_.get("fb_pixel") or [])] for s_ in lidos):
            raise RuntimeError(f"{ad_id}: pixel {pixel_id} não aparece na releitura")
        return True

    def conferir_anuncios(self, pai_id: str, expert: str) -> list[str]:
        """Pixel no tracking_specs, UTM em url_tags e link limpo em todos os anúncios de uma campanha/conjunto."""
        return problemas_anuncios(self.anuncios(pai_id), P.META_EXPERTS[expert]["pixel_id"])


# ---------------------------------------------------------------------------- funções puras (testadas)
def _norm_nome(v: str) -> str:
    v = unicodedata.normalize("NFKD", v or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", v)


def _sha(v: str) -> str:
    return hashlib.sha256(v.encode("utf-8")).hexdigest() if v else ""


def telefone_e164(v: Any) -> str:
    """'(11) 98888-7777' / '11988887777' / '5511988887777' / 11988887777.0 → '5511988887777'."""
    d = re.sub(r"\D", "", str(v or "").split(".")[0] if isinstance(v, float) else str(v or ""))
    if not d:
        return ""
    return d if d.startswith("55") and len(d) >= 12 else "55" + d


def linha_hash(p: dict) -> list[str]:
    """Linha no schema EMAIL, PHONE, FN, LN, COUNTRY — normalizado como o Meta pede, com SHA-256."""
    return [_sha((p.get("email") or "").strip().lower()), _sha(telefone_e164(p.get("phone"))),
            _sha(_norm_nome(p.get("first_name", ""))), _sha(_norm_nome(p.get("last_name", ""))), _sha("br")]


def asset_feed_por_posicionamento(tipo: str, feed_id: str, story_id: str, texto: str, link: str,
                                  titulo: str = "", descricao: str = "", cta: str = "LEARN_MORE") -> dict:
    """Um anúncio com mídia diferente no feed e no story/reels — a estrutura que funciona (itens 79 e
    memória de feed+story). `tipo`: 'video' (ids de vídeo) ou 'image' (image_hash)."""
    assert tipo in ("video", "image")
    midia, rotulo = ("videos", "video_label") if tipo == "video" else ("images", "image_label")
    chave = "video_id" if tipo == "video" else "hash"
    spec = {
        midia: [{chave: story_id, "adlabels": [{"name": "midia_story"}]},
                {chave: feed_id, "adlabels": [{"name": "midia_feed"}]}],
        "bodies": [{"text": texto, "adlabels": [{"name": "texto_story"}, {"name": "texto_feed"}]}],
        "link_urls": [{"website_url": link, "adlabels": [{"name": "link_story"}, {"name": "link_feed"}]}],
        "call_to_action_types": [cta],
        "ad_formats": ["AUTOMATIC_FORMAT"],
        "optimization_type": "PLACEMENT",
        "asset_customization_rules": [
            {"customization_spec": {"age_min": 13, "age_max": 65, "publisher_platforms": ["facebook", "instagram"],
                                    "facebook_positions": ["story", "facebook_reels"],
                                    "instagram_positions": ["story", "reels"]},
             rotulo: {"name": "midia_story"}, "body_label": {"name": "texto_story"},
             "link_url_label": {"name": "link_story"}, "priority": 1},
            {"customization_spec": {"age_min": 13, "age_max": 65},
             rotulo: {"name": "midia_feed"}, "body_label": {"name": "texto_feed"},
             "link_url_label": {"name": "link_feed"}, "priority": 2},
        ],
    }
    if titulo:
        spec["titles"] = [{"text": titulo}]
    if descricao:
        spec["descriptions"] = [{"text": descricao}]
    return spec


def targeting_padrao(publico_ids: list[str], excluidos: list[str] | None = None, *, sao_paulo: bool = False,
                     reels: bool = False) -> dict:
    """Targeting da casa: 25–55, geo BR (ou estado de SP no PES), advantage_audience 0, e Story+Reels
    quando a campanha é de reels."""
    t = {"age_min": P.IDADE_MIN, "age_max": P.IDADE_MAX,
         "geo_locations": P.GEO_SAO_PAULO if sao_paulo else P.GEO_BRASIL,
         "custom_audiences": [{"id": i} for i in publico_ids],
         "excluded_custom_audiences": [{"id": i} for i in (excluidos or [])],
         "targeting_automation": {"advantage_audience": 0}}
    if reels:
        t.update(P.POSICOES_REELS)
    return t


def links_do_criativo(creative: dict) -> list[str]:
    oss, afs = creative.get("object_story_spec") or {}, creative.get("asset_feed_spec") or {}
    links = [u.get("website_url", "") for u in afs.get("link_urls", [])]
    ld, vd = oss.get("link_data") or {}, oss.get("video_data") or {}
    links += [ld.get("link", "")] + [c.get("link", "") for c in ld.get("child_attachments", [])]
    links.append(((vd.get("call_to_action") or {}).get("value") or {}).get("link", ""))
    return [l for l in links if l]


def regra_site_por_url(pixel_ids: list[str], url_contem: list[str], dias: int = 180) -> dict:
    """Regra de público de site (visitou URL) no formato que o editor do Gerenciador abre.

    A forma "natural" pela API — filter {operator: or, filters: [urls]} — funciona, mas a interface responde
    "regra criada por API… sintaxe que não aceitamos" e não deixa editar. O editor grava sempre um AND com o
    grupo OR das URLs + um filtro de URL vazio; repetir isso mantém o público editável à mão (BV-26, item 191).
    Vários pixels entram como várias `event_sources` — a conta dona do público precisa ter acesso a todos."""
    return {"inclusions": {"operator": "or", "rules": [{
        "event_sources": [{"type": "pixel", "id": int(p)} for p in pixel_ids],
        "retention_seconds": dias * 86400,
        "filter": {"operator": "and", "filters": [
            {"operator": "or", "filters": [{"field": "url", "operator": "i_contains", "value": u} for u in url_contem]},
            {"field": "url", "operator": "i_contains", "value": ""}]},
        "template": "VISITORS_BY_URL"}]}}


def problemas_anuncios(ads: list[dict], pixel_id: str) -> list[str]:
    """Checklist de anúncio: pixel no tracking_specs, url_tags = UTM padrão, link sem UTM colada."""
    out = []
    for ad in ads:
        nome = ad.get("name", ad.get("id"))
        pixels = [str(p) for s in ad.get("tracking_specs", []) for p in (s.get("fb_pixel") or [])]
        if pixel_id not in pixels:
            out.append(f"{nome}: sem o pixel {pixel_id} no tracking_specs")
        cr = ad.get("creative") or {}
        if cr and cr.get("url_tags") != P.UTM_META:
            out.append(f"{nome}: url_tags diferente da UTM padrão ({(cr.get('url_tags') or 'vazio')[:40]})")
        for link in links_do_criativo(cr):
            if "utm_" in link:
                out.append(f"{nome}: UTM colada no link {link[:60]}")
    return out


def problemas_adset(adset: dict, nome_campanha: str) -> list[str]:
    """Checklist de conjunto: idade 25–55, advantage declarado, data de fim, e Reels sem Feed."""
    t, nome, out = adset.get("targeting") or {}, adset.get("name", adset.get("id")), []
    if (t.get("age_min"), t.get("age_max")) != (P.IDADE_MIN, P.IDADE_MAX):
        out.append(f"{nome}: idade {t.get('age_min')}–{t.get('age_max')} (padrão {P.IDADE_MIN}–{P.IDADE_MAX})")
    if "targeting_automation" not in t:
        out.append(f"{nome}: sem targeting_automation.advantage_audience")
    if not adset.get("end_time"):
        out.append(f"{nome}: sem data de fim (end_time)")
    if "reels" in nome_campanha.lower():
        pos = set(t.get("facebook_positions", [])) | set(t.get("instagram_positions", []))
        if not t.get("facebook_positions") or pos - {"story", "facebook_reels", "reels"}:
            out.append(f"{nome}: campanha de reels com posicionamento {sorted(pos) or 'automático'} (só Story+Reels)")
    return out


def expert_do_nome(nome: str) -> str | None:
    n = nome.lower()
    return next((e for e in P.EXPERTS if f"[{e}]" in n), None)
