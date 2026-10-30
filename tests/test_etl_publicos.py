"""Partes puras de etl/etl_publicos.py (sem rede, sem banco)."""
import pathlib
import sys

_RAIZ = pathlib.Path(__file__).resolve().parent.parent
for p in (_RAIZ / "etl", _RAIZ / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import etl_publicos as E  # noqa: E402

BASE = {"lancamento_codigo": "PES-NOV-26", "plataforma": "meta", "conta": "act_1", "campanha_id": "9",
        "campanha_nome": "[FB][captação][quente][PES-NOV-26]", "campanha_status": "ACTIVE"}


def test_meta_piso_de_1000_e_desconhecido():
    n = E.normalizar_publico_meta({"id": "1", "name": "x", "subtype": "CUSTOM", "approximate_count_lower_bound": 1000,
                                   "approximate_count_upper_bound": 1200, "delivery_status": {"code": 200},
                                   "operation_status": {"code": 200, "description": "Normal"}, "retention_days": 30,
                                   "time_content_updated": 1760000000})
    assert (n["tamanho_inferior"], n["tamanho_superior"], n["tamanho_efetivo"]) == (1000, 1200, 1000)
    assert n["status"] == 200 and n["retencao_dias"] == 30 and n["atualizado_em"] is not None
    desconhecido = E.normalizar_publico_meta({"id": "2", "approximate_count_lower_bound": -1})
    assert desconhecido["tamanho_efetivo"] is None and desconhecido["atualizado_em"] is None


def test_google_tamanho_efetivo_e_elegibilidade():
    n = E.normalizar_lista_google({"id": "7", "name": "L", "type": "CRM_BASED", "membershipStatus": "OPEN",
                                   "sizeForDisplay": "300", "sizeForSearch": "450", "eligibleForDisplay": False,
                                   "eligibleForSearch": True, "membershipLifeSpan": "10000",
                                   "matchRatePercentage": 61}, "123")
    assert n["tamanho_efetivo"] == 450 and n["elegivel"] is True and n["match_rate"] == 61.0
    assert "display=não" in n["status_detalhe"] and n["conta"] == "123"
    vazio = E.normalizar_lista_google({"id": "8", "sizeForDisplay": "0", "sizeForSearch": "0"}, "123")
    assert vazio["tamanho_efetivo"] == 0 and vazio["elegivel"] is None
    sem = E.normalizar_lista_google({"id": "9"}, "123")
    assert sem["tamanho_efetivo"] is None


def test_tipos_de_uso():
    assert E.tipo_uso_meta("LOOKALIKE") == "SEMELHANTE" and E.tipo_uso_meta("WEBSITE") == "SITE"
    assert E.tipo_uso_meta("CUSTOM") == "LISTA" and E.tipo_uso_meta("VIDEO") == "ENGAJAMENTO"
    assert E.tipo_uso_meta(None, "Semelhante (1%) - x") == "SEMELHANTE"
    assert E.tipo_uso_google("CRM_BASED") == "LISTA" and E.tipo_uso_google("RULE_BASED") == "SITE"
    assert E.tipo_uso_google("LOGICAL") == "COMBINADO" and E.tipo_uso_google(None) == "OUTRO"


def test_usos_adset_meta_inclui_exclui_e_interesses():
    adset = {"id": "55", "name": "00 - Interesses", "effective_status": "ACTIVE", "targeting": {
        "custom_audiences": [{"id": "10", "name": "Semelhante (1%) - A"}],
        "excluded_custom_audiences": [{"id": "20"}],
        "flexible_spec": [{"interests": [{"id": "6003", "name": "Direito"}]}],
        "exclusions": {"interests": [{"id": "6004", "name": "Concursos"}]}}}
    snaps = {"20": {"nome": "[Lista] Alunos", "tipo": "CUSTOM"}}
    u = E.usos_adset_meta(BASE, adset, snaps)
    por = {(x["publico_id"], x["papel"]): x for x in u}
    assert por[("10", "inclui")]["publico_tipo"] == "SEMELHANTE"
    assert por[("20", "exclui")]["publico_nome"] == "[Lista] Alunos" and por[("20", "exclui")]["publico_tipo"] == "LISTA"
    assert por[("6003", "inclui")]["publico_tipo"] == "INTERESSE" and por[("6004", "exclui")]["publico_nome"] == "Concursos"
    assert all(x["grupo_id"] == "55" and x["grupo_status"] == "ACTIVE" for x in u)


def test_usos_grupo_google_com_segmentos():
    gr = {"id": "77", "nome": "G1", "status": "ENABLED", "incluidos": {"1": "Lista A"}, "excluidos": {"2": "Alunos"},
          "segmentos": ["Segmento personalizado: Direito", "Interesse: Concursos"]}
    u = E.usos_grupo_google({**BASE, "plataforma": "google"}, gr, {"1": {"tipo": "CRM_BASED"}})
    por = {(x["publico_nome"], x["papel"]): x for x in u}
    assert por[("Lista A", "inclui")]["publico_tipo"] == "LISTA"
    assert por[("Alunos", "exclui")]["publico_tipo"] == "OUTRO"
    assert por[("Segmento personalizado: Direito", "inclui")]["publico_tipo"] == "SEGMENTO"
    assert por[("Interesse: Concursos", "inclui")]["publico_tipo"] == "INTERESSE"
    assert por[("Interesse: Concursos", "inclui")]["publico_id"] == E.id_segmento_google("Interesse: Concursos")


def test_chave_primaria_de_uso_sem_duplicata():
    adset = {"id": "1", "targeting": {"custom_audiences": [{"id": "10", "name": "A"}, {"id": "10", "name": "A"}]}}
    chaves = {(x["grupo_id"], x["publico_id"], x["papel"]) for x in E.usos_adset_meta(BASE, adset, {})}
    assert len(chaves) == 1


def test_grupo_sem_publico_vira_marcador_nenhum():
    meta = E.usos_adset_meta(BASE, {"id": "1", "name": "Aberto", "targeting": {}}, {})
    assert len(meta) == 1 and meta[0]["papel"] == "nenhum" and meta[0]["grupo_id"] == "1"
    google = E.usos_grupo_google(BASE, {"id": "2", "nome": "G", "status": "ENABLED", "incluidos": {}, "excluidos": {},
                                         "segmentos": []}, {})
    assert len(google) == 1 and google[0]["papel"] == "nenhum"
