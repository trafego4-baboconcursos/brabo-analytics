"""
Testes para frontend/core.py — funções de negócio sem dependência de DB ou disco.
"""
from __future__ import annotations
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Garante que src/ e raiz estão no path antes de importar core
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from frontend.core import (
    fmt_brl, fmt_num, fmt_pct,
    _norm_text, _extract_ad_code,
    _classify_campaign, _classify_google_campaign_type,
    _utm_score, _inc_sales,
    find_previous_launch, resolve_launch,
)


# ── Formatadores ───────────────────────────────────────────────────────────────

class TestFmtBrl:
    def test_inteiro(self):
        assert fmt_brl(1234) == "R$ 1.234,00"

    def test_decimal(self):
        assert fmt_brl(1234.56) == "R$ 1.234,56"

    def test_zero(self):
        assert fmt_brl(0) == "R$ 0,00"

    def test_valor_invalido(self):
        assert fmt_brl(None) == "R$ 0,00"

    def test_sem_decimais(self):
        assert fmt_brl(1000, decimals=0) == "R$ 1.000"

    def test_milhar(self):
        assert fmt_brl(1_000_000) == "R$ 1.000.000,00"


class TestFmtNum:
    def test_inteiro(self):
        assert fmt_num(1234) == "1.234"

    def test_com_decimal(self):
        assert fmt_num(1234.5, decimals=1) == "1.234,5"

    def test_zero(self):
        assert fmt_num(0) == "0"

    def test_invalido(self):
        assert fmt_num(None) == "0"


class TestFmtPct:
    def test_basico(self):
        assert fmt_pct(12.5) == "12.5%"

    def test_zero(self):
        assert fmt_pct(0) == "0.0%"

    def test_invalido(self):
        assert fmt_pct(None) == "0%"

    def test_decimais(self):
        assert fmt_pct(33.333, decimals=2) == "33.33%"


# ── _norm_text ─────────────────────────────────────────────────────────────────

class TestNormText:
    def test_acento_removido(self):
        assert _norm_text("Captação") == "captacao"

    def test_maiuscula_para_minuscula(self):
        assert _norm_text("META ADS") == "meta ads"

    def test_espacos_preservados(self):
        assert _norm_text("  hello  ") == "hello"

    def test_none_like(self):
        assert _norm_text("") == ""

    def test_cedilha(self):
        assert _norm_text("Pré-Qualificação") == "pre-qualificacao"


# ── _extract_ad_code ───────────────────────────────────────────────────────────

class TestExtractAdCode:
    def test_simples(self):
        assert _extract_ad_code("AD110 - Banco do Brasil") == "AD110"

    def test_minusculo(self):
        assert _extract_ad_code("ad22 - criativo") == "AD22"

    def test_no_codigo(self):
        assert _extract_ad_code("captação genérica sem código") == ""

    def test_no_meio_da_string(self):
        assert _extract_ad_code("[MA][captacao][PBB-ABR-26] AD205 variante") == "AD205"

    def test_utm_content(self):
        assert _extract_ad_code("AD999") == "AD999"

    def test_string_vazia(self):
        assert _extract_ad_code("") == ""

    def test_none_like(self):
        assert _extract_ad_code(None) == ""


# ── _classify_campaign ────────────────────────────────────────────────────────

class TestClassifyCampaign:
    def test_meta_por_source(self):
        r = _classify_campaign("campanha x", source="facebook")
        assert r["channel"] == "Meta Ads"

    def test_meta_por_tag_ma(self):
        r = _classify_campaign("[MA][captacao]")
        assert r["channel"] == "Meta Ads"

    def test_google_por_source(self):
        r = _classify_campaign("campanha y", source="google")
        assert r["channel"] == "Google Ads"

    def test_google_por_tag_ga(self):
        r = _classify_campaign("[GA][captacao][PBB-ABR-26]")
        assert r["channel"] == "Google Ads"

    def test_etapa_captacao(self):
        r = _classify_campaign("captacao frio facebook")
        assert r["etapa"] == "Captação"

    def test_etapa_pitch(self):
        r = _classify_campaign("[MA][matriculas][PBB-ABR-26]")
        assert r["etapa"] == "Pitch/ROAS"

    def test_etapa_rmk(self):
        r = _classify_campaign("engajamento quente")
        assert r["etapa"] == "RMK/Engajamento"

    def test_temperatura_quente(self):
        r = _classify_campaign("captacao quente")
        assert r["temperatura"] == "Quente"

    def test_temperatura_frio(self):
        r = _classify_campaign("captacao frio lookalike")
        assert r["temperatura"] == "Frio"

    def test_bucket_principal(self):
        r = _classify_campaign("captacao principal")
        assert r["bucket"] == "Principal"

    def test_sem_classificacao(self):
        r = _classify_campaign("campanha sem tag")
        assert r["channel"] == "Outros"
        assert r["etapa"] == "Outros"


# ── _classify_google_campaign_type ────────────────────────────────────────────

class TestClassifyGoogleCampaignType:
    def test_pmax(self):
        assert _classify_google_campaign_type(campaign="pmax captacao") == "PMax"

    def test_performance_max(self):
        assert _classify_google_campaign_type(campaign="performance max") == "PMax"

    def test_search(self):
        assert _classify_google_campaign_type(campaign="search captacao") == "Search"

    def test_display(self):
        assert _classify_google_campaign_type(campaign="display gdn") == "Display"

    def test_youtube(self):
        assert _classify_google_campaign_type(campaign="youtube captacao") == "YouTube"

    def test_geracao_demanda(self):
        assert _classify_google_campaign_type(campaign="geracao de demanda") == "Geração de demanda"

    def test_ga_tag_com_captacao(self):
        assert _classify_google_campaign_type(campaign="[ga][captacao]") == "Geração de demanda"

    def test_desconhecido(self):
        assert _classify_google_campaign_type(campaign="campanha sem tipo") == "Google sem AD"


# ── _utm_score ────────────────────────────────────────────────────────────────

class TestUtmScore:
    def test_score_zero_sem_utm(self):
        score = _utm_score("PBB-ABR-26", "", "", "", "")
        assert score == 0

    def test_score_aumenta_com_source(self):
        score = _utm_score("PBB-ABR-26", "facebook", "cpc", "", "")
        assert score > 0

    def test_launch_code_no_utm_aumenta_score(self):
        com = _utm_score("PBB-ABR-26", "facebook", "cpc", "[MA][captacao][PBB-ABR-26]", "AD110")
        sem = _utm_score("PBB-ABR-26", "facebook", "cpc", "[MA][captacao][PES-MAI-26]", "AD110")
        assert com > sem

    def test_ad_code_no_utm_aumenta_score(self):
        com = _utm_score("PBB-ABR-26", "facebook", "cpc", "AD110", "")
        sem = _utm_score("PBB-ABR-26", "facebook", "cpc", "sem-ad", "")
        assert com > sem

    def test_meta_score_maior_que_outros(self):
        meta = _utm_score("PBB-ABR-26", "facebook", "cpc", "captacao", "")
        outros = _utm_score("PBB-ABR-26", "email", "newsletter", "promo", "")
        assert meta > outros


# ── _inc_sales ────────────────────────────────────────────────────────────────

class TestIncSales:
    def test_cria_chave_nova(self):
        target = {}
        _inc_sales(target, "Meta Ads", receita=100.0, vendas=1)
        assert target["Meta Ads"]["vendas"] == 1
        assert target["Meta Ads"]["faturamento"] == 100.0

    def test_acumula_na_mesma_chave(self):
        target = {}
        _inc_sales(target, "Meta Ads", receita=100.0, vendas=1)
        _inc_sales(target, "Meta Ads", receita=200.0, vendas=2)
        assert target["Meta Ads"]["vendas"] == 3
        assert target["Meta Ads"]["faturamento"] == 300.0

    def test_chaves_independentes(self):
        target = {}
        _inc_sales(target, "Meta Ads", receita=100.0)
        _inc_sales(target, "Google Ads", receita=50.0)
        assert "Meta Ads" in target
        assert "Google Ads" in target
        assert target["Meta Ads"]["faturamento"] != target["Google Ads"]["faturamento"]


# ── find_previous_launch ──────────────────────────────────────────────────────

def _make_launch(code: str, product: str, data_inicio: date) -> object:
    return SimpleNamespace(
        code=code,
        product=product,
        data_inicio=data_inicio,
        has_meta=True, has_google=True, has_vendas=True,
        has_ac=False, has_typeform=False,
    )


class TestFindPreviousLaunch:
    def test_retorna_lancamento_anterior(self):
        pbb1 = _make_launch("PBB-JAN-26", "PBB", date(2026, 1, 1))
        pbb2 = _make_launch("PBB-ABR-26", "PBB", date(2026, 4, 1))
        result = find_previous_launch(pbb2, [pbb1, pbb2])
        assert result.code == "PBB-JAN-26"

    def test_ignora_produto_diferente(self):
        pbb1 = _make_launch("PBB-JAN-26", "PBB", date(2026, 1, 1))
        pes1 = _make_launch("PES-ABR-26", "PES", date(2026, 4, 1))
        result = find_previous_launch(pes1, [pbb1, pes1])
        assert result is None

    def test_retorna_mais_recente_entre_anteriores(self):
        pbb1 = _make_launch("PBB-JAN-26", "PBB", date(2026, 1, 1))
        pbb2 = _make_launch("PBB-FEV-26", "PBB", date(2026, 2, 1))
        pbb3 = _make_launch("PBB-ABR-26", "PBB", date(2026, 4, 1))
        result = find_previous_launch(pbb3, [pbb1, pbb2, pbb3])
        assert result.code == "PBB-FEV-26"

    def test_sem_lancamento_anterior(self):
        pbb1 = _make_launch("PBB-JAN-26", "PBB", date(2026, 1, 1))
        result = find_previous_launch(pbb1, [pbb1])
        assert result is None

    def test_launch_sem_data_retorna_none(self):
        launch = SimpleNamespace(code="X", product="PBB", data_inicio=None)
        result = find_previous_launch(launch, [launch])
        assert result is None


# ── resolve_launch ────────────────────────────────────────────────────────────

class TestResolveLaunch:
    def test_por_codigo(self):
        pbb = _make_launch("PBB-ABR-26", "PBB", date(2026, 4, 1))
        pes = _make_launch("PES-MAI-26", "PES", date(2026, 5, 1))
        # resolve_launch chama get_launch do database_reader internamente
        # testamos via mock do módulo
        from unittest.mock import patch
        with patch("frontend.core.get_launch", return_value=pes) as mock_get:
            result = resolve_launch("PES-MAI-26", [pbb, pes])
            mock_get.assert_called_once_with([pbb, pes], "PES-MAI-26")
            assert result == pes

    def test_sem_codigo_prefere_com_todos_os_dados(self):
        completo = _make_launch("PBB-ABR-26", "PBB", date(2026, 4, 1))
        parcial = SimpleNamespace(
            code="PES-MAI-26", product="PES", data_inicio=date(2026, 5, 1),
            has_meta=True, has_google=False, has_vendas=False,
            has_ac=False, has_typeform=False,
        )
        result = resolve_launch(None, [completo, parcial])
        assert result.code == "PBB-ABR-26"

    def test_lista_vazia_retorna_none(self):
        result = resolve_launch(None, [])
        assert result is None
