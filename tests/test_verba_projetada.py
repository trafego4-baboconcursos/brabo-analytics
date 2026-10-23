from frontend.services.verba_projetada import verba_projetada_da_etapa

CFG = {"etapas": [
    {"nome": "Pré-Qualificação", "total": 150000, "buckets": [
        {"pct": 31.8, "nome": "FB Frio", "plataforma": "meta"}, {"pct": 15.9, "nome": "FB Quente", "plataforma": "meta"},
        {"pct": 5.3, "nome": "FB Específico", "plataforma": "meta"}, {"pct": 28.2, "nome": "YT Frio", "plataforma": "google"},
        {"pct": 18.8, "nome": "YT Quente", "plataforma": "google"}]},
    {"nome": "Lembrete", "total": 3312, "buckets": []},
    {"nome": "Zerada", "total": 0, "buckets": [{"pct": 100, "plataforma": "meta"}]},
]}


def test_projetado_por_plataforma_e_o_total_da_etapa_vezes_a_soma_dos_percentuais():
    v = verba_projetada_da_etapa(CFG, "Pré-Qualificação")
    assert v["total"] == 150000
    assert round(v["meta"], 2) == 79500.0       # 31,8 + 15,9 + 5,3 = 53%
    assert round(v["google"], 2) == 70500.0     # 28,2 + 18,8 = 47%


def test_nome_da_etapa_ignora_acento_e_caixa():
    assert verba_projetada_da_etapa(CFG, "pre-qualificacao")["total"] == 150000   # sem acento casa
    assert verba_projetada_da_etapa(CFG, "PRÉ-QUALIFICAÇÃO")["total"] == 150000   # caixa não importa
    assert verba_projetada_da_etapa(CFG, "PRE QUALIFICACAO") is None              # o hífen faz parte do nome


def test_etapa_sem_buckets_devolve_so_o_total_e_etapa_inexistente_ou_zerada_devolve_none():
    v = verba_projetada_da_etapa(CFG, "Lembrete")
    assert v == {"total": 3312.0, "meta": None, "google": None}
    assert verba_projetada_da_etapa(CFG, "Aquecimento") is None
    assert verba_projetada_da_etapa(CFG, "Zerada") is None
    assert verba_projetada_da_etapa({}, "Pré-Qualificação") is None
    assert verba_projetada_da_etapa(None, "x") is None
