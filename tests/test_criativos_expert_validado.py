"""Expert e selo Validado/Novo dos criativos da Black (10/10/26)."""
from src.nomenclatura import expert_do_codigo, normalizar_nome_criativo, selo_validacao


def test_expert_pelo_prefixo():
    assert expert_do_codigo("ADC-MA38") == "Mateus"
    assert expert_do_codigo("AD-IV09") == "Ivan"
    assert expert_do_codigo("ADC-FE02") == "Felipe"
    assert expert_do_codigo("AD-TR24") == "Trio/misto"
    assert expert_do_codigo("AD123") == "Sem expert"


def test_nome_ignora_codigo_tag_acento_e_pontuacao():
    a = normalizar_nome_criativo("AD-FE05 - Música - BV25")
    b = normalizar_nome_criativo("AD-FE05 - Musica - BV-26")
    assert a == b == "musica"


def test_selo_mesmo_codigo_mesmo_nome_e_validado():
    hist = {"AD-FE02": {normalizar_nome_criativo("AD-FE02 - Caixinha de perguntas - BV-25")}}
    assert selo_validacao("AD-FE02", "AD-FE02 - Caixinha de perguntas - BV-26", hist) == "validado"


def test_selo_codigo_reaproveitado_com_outro_video():
    hist = {"AD-IV09": {normalizar_nome_criativo("AD-IV09 - caixinha de pergunta - BV-25")}}
    assert selo_validacao("AD-IV09", "AD-IV09 - Tudo em 1 min", hist) == "reaproveitado"


def test_selo_codigo_inedito_e_novo():
    assert selo_validacao("ADC-MA99", "ADC-MA99 - x", {"AD-IV09": {"x"}}) == "novo"
