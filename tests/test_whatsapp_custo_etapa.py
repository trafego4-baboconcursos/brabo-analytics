"""custo_por_etapa: custo diário do WhatsApp repartido pelas datas das etapas (29/10/26)."""
from frontend.db_readers.whatsapp_messages import custo_por_etapa

CFG = {
    "pre_quali_start_date": "2026-10-12", "pre_quali_end_date": "2026-11-13",
    "captacao_start_date": "2026-11-02", "captacao_end_date": "2026-11-16",
    "evento_start_date": "2026-11-16", "evento_end_date": "2026-11-19",
    "carrinho_start_date": "2026-11-19", "carrinho_end_date": "2026-11-30",
}


def _wa(*dias):
    return {"accounts": [{"series": [{"date": d, "cost_brl": v} for d, v in dias]}]}


def test_sobreposicao_vai_para_a_etapa_mais_adiantada():
    r = custo_por_etapa(_wa(("2026-10-20", 10.0), ("2026-11-05", 20.0), ("2026-11-16", 30.0),
                            ("2026-11-19", 40.0), ("2026-12-01", 5.0), ("2026-11-10", None)), CFG)
    assert r == {"Pré-Qualificação": 10.0, "Captação": 20.0, "Aulas": 30.0, "Carrinho": 40.0, "Outros": 5.0}


def test_sem_dado_ou_sem_datas():
    assert sum(custo_por_etapa(None, CFG).values()) == 0
    assert custo_por_etapa(_wa(("2026-10-20", 7.0)), {})["Outros"] == 7.0
