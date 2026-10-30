"""frontend/db_readers/publicos.py — montagem da visão e alertas (pura, sem banco)."""
from datetime import date, datetime, timezone

from frontend.db_readers import publicos as R

HOJE = date(2026, 10, 30)
ALUNO_META = "120216438983140754"
CAD_META = "300"


def uso(plat, grupo, publico, nome, tipo, papel, *, camp="[MA][cadastro][captação][quente][principal][PES-NOV-26][26.10.26]",
        conta="act_1", status="ACTIVE"):
    return {"plataforma": plat, "conta": conta, "campanha_id": "c1", "campanha_nome": camp, "campanha_status": status,
            "grupo_id": grupo, "grupo_nome": f"conjunto {grupo}", "grupo_status": status, "publico_id": publico,
            "publico_nome": nome, "publico_tipo": tipo, "papel": papel}


def snap(plat, pid, nome, tam, **kw):
    conta = kw.pop("conta", "")
    return (plat, conta, pid), {"plataforma": plat, "conta": conta, "publico_id": pid, "nome": nome,
                                "tamanho_efetivo": tam, "tamanho_inferior": tam if plat == "meta" else None,
                                "tamanho_superior": None, "tipo": kw.pop("tipo", "CUSTOM"), "status": kw.pop("status", "200"),
                                "status_detalhe": "", "elegivel": kw.pop("elegivel", None), "retencao_dias": None,
                                "atualizado_em": kw.pop("atualizado_em", None), "coletado_em": datetime(2026, 10, 30, tzinfo=timezone.utc), **kw}


def visao(usos, snaps, desemp=None):
    return R.montar_visao("PES-NOV-26", usos, dict(snaps), desemp or {}, {}, HOJE)


def alertas(v, pid):
    return {a.codigo: a for p in v.publicos if p.id == pid for a in p.alertas}


def test_classificacao_de_campanha():
    assert R.temperatura_da_campanha("[MA][cadastro][captação][específico][x]") == "especifico"
    assert R.temperatura_da_campanha("[GA][pré-qualificação][frio][PES-NOV-26]") == "frio"
    assert R.etapa_da_campanha("[GA][pré-qualificação][frio]") == "pre_quali"
    assert R.etapa_da_campanha("[MA][cadastro][captação][quente]") == "captacao"


def test_rotulo_do_meta_nunca_diz_exato_no_piso():
    assert R.rotulo_tamanho("meta", 1000, 1000, 1200) == "≤ 1.000"
    assert R.rotulo_tamanho("meta", 21000, 21000, 25000) == "21.000–25.000"
    assert R.rotulo_tamanho("google", 450, None, None) == "450"
    assert R.rotulo_tamanho("google", None, None, None) == "—"


def test_lista_vazia_unica_do_grupo_e_critica_no_google():
    usos = [uso("google", "g1", "L1", "[M] Lista Leads", "LISTA", "inclui", conta="123",
                camp="[GA][cadastro][captação][quente][principal][PES-NOV-26][26.10.26]")]
    v = visao(usos, [snap("google", "L1", "[M] Lista Leads", 0, conta="123", status="OPEN")])
    a = alertas(v, "L1")
    assert a["vazia"].nivel == "critico" and "não entregam" in a["vazia"].texto
    assert v.publicos[0].severidade == "critico"


def test_lista_pequena_dentro_de_grupo_com_outras_e_so_atencao():
    usos = [uso("google", "g1", "L1", "Pequena", "LISTA", "inclui", conta="123"),
            uso("google", "g1", "L2", "Grande", "LISTA", "inclui", conta="123")]
    v = visao(usos, [snap("google", "L1", "Pequena", 8, conta="123"), snap("google", "L2", "Grande", 90000, conta="123")])
    assert alertas(v, "L1")["pequeno"].nivel == "atencao"
    assert "pequeno" not in alertas(v, "L2")


def test_publico_so_excluido_nao_gera_alerta_de_tamanho():
    usos = [uso("google", "g1", "L1", "Aluno", "LISTA", "exclui", conta="123")]
    v = visao(usos, [snap("google", "L1", "Aluno", 0, conta="123")])
    assert "vazia" not in alertas(v, "L1")


def test_seg4_aluno_e_cadastrado_faltando_e_frio_com_lista():
    camp = "[MA][cadastro][captação][frio][principal][PES-NOV-26][26.10.26]"
    usos = [uso("meta", "a1", ALUNO_META, "[Lista] Alunos Escrevente [PES-26]", "LISTA", "inclui", camp=camp),
            uso("meta", "a1", "10", "Semelhante (1%) - X", "SEMELHANTE", "inclui", camp=camp)]
    v = visao(usos, [snap("meta", ALUNO_META, "[Lista] Alunos Escrevente [PES-26]", 17900),
                     snap("meta", "10", "Semelhante (1%) - X", 5_000_000)])
    txt = " | ".join(v.grupos[0].problemas)
    assert "INCLUI a lista de alunos" in txt and "não exclui cadastrados do PES-NOV-26" in txt
    assert "frio com 1 público(s) próprio(s)" in txt
    assert any(a["nivel"] == "atencao" and "INCLUI a lista de alunos" in a["texto"] for a in v.atencao)


def test_grupo_correto_nao_tem_problema_e_lembrete_fica_fora_da_regra():
    camp = "[MA][cadastro][captação][quente][principal][PES-NOV-26][26.10.26]"
    usos = [uso("meta", "a1", ALUNO_META, "[Lista] Alunos Escrevente [PES-26]", "LISTA", "exclui", camp=camp),
            uso("meta", "a1", CAD_META, "[Lista] Cadastrados [PES-NOV-26]", "LISTA", "exclui", camp=camp),
            uso("meta", "a1", "55", "Viu Captação 50% - [PES-NOV-26]", "ENGAJAMENTO", "inclui", camp=camp),
            uso("meta", "b1", "55", "Viu Captação 50% - [PES-NOV-26]", "ENGAJAMENTO", "inclui",
                camp="[MA][lembrete][PES-NOV-26]")]
    v = visao(usos, [snap("meta", ALUNO_META, "x", 17900), snap("meta", CAD_META, "x", 1000),
                     snap("meta", "55", "Viu Captação 50% - [PES-NOV-26]", 21000)])
    por = {g.grupo_id: g for g in v.grupos}
    assert por["a1"].problemas == [] and por["b1"].problemas == []


def test_outro_lancamento_nome_repetido_e_lista_velha():
    usos = [uso("meta", "a1", "1", "Viu CPL [PES-MAI-26] - 30D", "ENGAJAMENTO", "inclui"),
            uso("meta", "a1", "2", "[Lista] Leads", "LISTA", "inclui"),
            uso("meta", "a1", "3", "[Lista] Leads", "LISTA", "inclui")]
    velho = datetime(2026, 8, 1, tzinfo=timezone.utc)
    v = visao(usos, [snap("meta", "1", "Viu CPL [PES-MAI-26] - 30D", 4000), snap("meta", "2", "[Lista] Leads", 9000, atualizado_em=velho),
                     snap("meta", "3", "[Lista] Leads", 9500)])
    assert alertas(v, "1")["outro_lancamento"].nivel == "info"
    assert "nome_repetido" in alertas(v, "2") and "ID 3" in alertas(v, "2")["nome_repetido"].texto
    assert "lista_velha" in alertas(v, "2") and "lista_velha" not in alertas(v, "3")


def test_meta_status_de_entrega_diferente_de_200_alerta():
    usos = [uso("meta", "a1", "1", "Lista X", "LISTA", "inclui")]
    v = visao(usos, [snap("meta", "1", "Lista X", 1000, status="300")])
    assert "entrega" in alertas(v, "1")


def test_desempenho_do_publico_soma_conjuntos_que_incluem_sem_contar_exclusao():
    usos = [uso("meta", "a1", "1", "P", "ENGAJAMENTO", "inclui"), uso("meta", "a2", "1", "P", "ENGAJAMENTO", "inclui"),
            uso("meta", "a3", "1", "P", "ENGAJAMENTO", "exclui")]
    d = {("meta", "a1"): R.Desempenho(10, 2, 100, 20), ("meta", "a2"): R.Desempenho(5, 1, 50, 10),
         ("meta", "a3"): R.Desempenho(999, 9, 999, 9)}
    v = visao(usos, [snap("meta", "1", "P", 5000)], d)
    p = v.publicos[0]
    assert (p.n_inclui, p.n_exclui) == (2, 1)
    assert (p.desempenho.gasto_3d, p.desempenho.gasto) == (15, 150) and p.desempenho.cpl == 150 / 30


def test_grupo_sem_publico_aparece_e_google_aberto_vira_problema():
    camp = "[GA][cadastro][captação][quente][principal][PES-NOV-26][26.10.26]"
    usos = [dict(uso("google", "g9", "-", "(sem público)", "OUTRO", "nenhum", camp=camp, conta="123"))]
    v = visao(usos, [])
    assert len(v.grupos) == 1 and v.publicos == []
    assert any("sem público" in p for p in v.grupos[0].problemas)


def test_interesse_sem_tamanho_nao_alerta():
    usos = [uso("meta", "a1", "6003", "Direito", "INTERESSE", "inclui")]
    assert visao(usos, []).publicos[0].alertas == []
