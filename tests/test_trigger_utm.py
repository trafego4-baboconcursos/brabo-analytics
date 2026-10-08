"""O trigger que guarda a UTM antiga quando a `leads` a troca (etl/historico_utm_trigger.py).

Roda contra o banco REAL, mas só dentro de uma transação desfeita no fim: as tabelas
`zz_*` e o trigger de teste nunca existem para ninguém além desta conexão, e a `leads`
verdadeira não é tocada. Sem banco acessível (CI, sem rede), os testes são pulados.

O que está em jogo: um defeito no trigger pode bloquear a gravação na `leads` — que o
ETL e o upsert em tempo real do Mateus fazem — então o caso "falha no histórico não
derruba a `leads`" é o mais importante do arquivo.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
# Mesma ordem do ETL: etl/ na frente, senão o pacote src/db sombreia o etl/db.py.
sys.path.insert(0, str(_RAIZ / "src"))
sys.path.insert(0, str(_RAIZ / "etl"))
sys.path.insert(0, str(_RAIZ))

import historico_utm_trigger as ht  # noqa: E402

N = ht.Nomes.teste()
CAMPOS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")

PI = "[MA][cadastro][captação][quente][principal][PI-AGO-26][20.07.26]"
PI2 = "[GA][captação][frio][principal][PI-AGO-26][27.07.26]"
BF = "[MA][mateus][captação][base forte][alunos][principal][BV-26][28.09.26]"
BV = "[MA][mateus][captação][black-vitalícia][super quente][BV-26][06.10.26]"


@pytest.fixture(scope="module")
def cur():
    """Cursor numa transação que NUNCA é confirmada."""
    try:
        from frontend.db import _get_engine  # noqa: PLC0415
        conn = _get_engine().raw_connection()
        c = conn.cursor()
        c.execute("SELECT 1")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"banco indisponível: {type(e).__name__}")
    try:
        c.execute(f"CREATE TABLE {N.leads} (LIKE leads INCLUDING ALL)")
        c.execute(f"CREATE TABLE {N.estado} (LIKE lead_utm_lancamento INCLUDING ALL)")
        for comando in ht.ddl_completo(N):
            c.execute(comando)
        c.execute(ht.ddl_visao(N))
        yield c
    finally:
        conn.rollback()
        conn.close()


def _upsert(c, cid, campanha, content="AD100", term="", source="facebook", email=None):
    c.execute(
        f"""INSERT INTO {N.leads} (id, email, utm_source, utm_medium, utm_campaign, utm_content, utm_term)
            VALUES (%s, %s, %s, 'cpc', %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET utm_source = EXCLUDED.utm_source,
              utm_medium = EXCLUDED.utm_medium, utm_campaign = EXCLUDED.utm_campaign,
              utm_content = EXCLUDED.utm_content, utm_term = EXCLUDED.utm_term""",
        (cid, email or f"{cid}@teste.com", source, campanha, content, term))


def _estado(c, cid):
    c.execute(f"""SELECT lancamento_codigo, trilha, utm_campaign, utm_content FROM {N.estado}
                  WHERE contact_id = %s ORDER BY 1, 2""", (cid,))
    return c.fetchall()


def _historico(c, cid):
    c.execute(f"""SELECT lancamento_codigo, trilha, utm_campaign, utm_content FROM {N.historico}
                  WHERE contact_id = %s ORDER BY substituida_em, utm_content""", (cid,))
    return c.fetchall()


def test_contato_novo_com_utm_de_lancamento_entra_no_estado(cur):
    _upsert(cur, "t1", PI)
    assert _estado(cur, "t1") == [("PI-AGO-26", "", PI, "AD100")]
    assert _historico(cur, "t1") == []


def test_utm_sem_codigo_de_lancamento_nao_entra(cur):
    """link_bio, {{campaign.name}} e vazio não nomeiam lançamento: nem linha, nem sobrescrita."""
    _upsert(cur, "t2", "link_bio")
    _upsert(cur, "t2b", "{{campaign.name}}")
    cur.execute(f"INSERT INTO {N.leads} (id, email) VALUES ('t2c', 'sem-utm@teste.com')")
    assert _estado(cur, "t2") == [] and _estado(cur, "t2b") == [] and _estado(cur, "t2c") == []


def test_mesmo_lancamento_utm_nova_vira_atual_e_a_antiga_vai_pro_historico(cur):
    _upsert(cur, "t3", PI, content="AD100")
    _upsert(cur, "t3", PI2, content="AD400")
    assert _estado(cur, "t3") == [("PI-AGO-26", "", PI2, "AD400")]       # a última vence
    assert _historico(cur, "t3") == [("PI-AGO-26", "", PI, "AD100")]     # a antiga NÃO se perde


def test_outro_lancamento_nao_toca_na_linha_do_anterior(cur):
    """O caso que motivou tudo: cliente da base entra na Black."""
    _upsert(cur, "t4", PI, content="AD100")
    _upsert(cur, "t4", BF, content="AD-BF01")
    assert _estado(cur, "t4") == [("BV-26", "Base Forte", BF, "AD-BF01"),
                                  ("PI-AGO-26", "", PI, "AD100")]
    assert _historico(cur, "t4") == []        # nada foi substituído, só acrescentado


def test_trilhas_da_black_ficam_em_linhas_separadas(cur):
    _upsert(cur, "t5", BF, content="AD-BF01")
    _upsert(cur, "t5", BV, content="AD-BV07")
    assert [(l, t) for l, t, *_ in _estado(cur, "t5")] == [("BV-26", "Base Forte"), ("BV-26", "Black Vitalícia")]
    assert _historico(cur, "t5") == []


def test_utm_sem_codigo_depois_de_uma_boa_nao_apaga_a_boa(cur):
    """A `leads` pode ficar com `link_bio`; o estado e o histórico mantêm a UTM do lançamento."""
    _upsert(cur, "t6", PI, content="AD100")
    _upsert(cur, "t6", "link_bio")
    assert _estado(cur, "t6") == [("PI-AGO-26", "", PI, "AD100")]


def test_atualizar_outra_coisa_sem_mudar_a_utm_nao_faz_nada(cur):
    _upsert(cur, "t7", PI)
    cur.execute(f"SELECT ultimo_visto_em FROM {N.estado} WHERE contact_id = 't7'")
    antes = cur.fetchone()[0]
    time.sleep(0.05)
    cur.execute(f"UPDATE {N.leads} SET nome = 'Fulano' WHERE id = 't7'")
    cur.execute(f"SELECT ultimo_visto_em FROM {N.estado} WHERE contact_id = 't7'")
    assert cur.fetchone()[0] == antes
    assert _historico(cur, "t7") == []


def test_voltar_para_a_utm_anterior_nao_duplica(cur):
    _upsert(cur, "t8", PI, content="AD100")
    _upsert(cur, "t8", PI2, content="AD400")
    _upsert(cur, "t8", PI, content="AD100")
    assert _estado(cur, "t8") == [("PI-AGO-26", "", PI, "AD100")]
    assert sorted(h[3] for h in _historico(cur, "t8")) == ["AD100", "AD400"]   # cada uma, uma vez


def test_maiuscula_e_espaco_nas_pontas_nao_criam_utm_nova(cur):
    _upsert(cur, "t9", PI, content="AD100")
    _upsert(cur, "t9", f"  {PI.upper()}  ", content="ad100")
    assert _historico(cur, "t9") == []


def test_falha_no_historico_nao_derruba_a_gravacao_na_leads(cur):
    """O ponto mais importante: se o trigger quebrar, a `leads` grava do mesmo jeito."""
    _upsert(cur, "t10", PI, content="AD100")
    cur.execute("SAVEPOINT quebra")
    try:
        cur.execute(f"ALTER TABLE {N.historico} DROP COLUMN utm_term")   # força o erro dentro do trigger
        _upsert(cur, "t10", PI2, content="AD400")                        # NÃO pode levantar exceção
        cur.execute(f"SELECT utm_content FROM {N.leads} WHERE id = 't10'")
        assert cur.fetchone()[0] == "AD400"                              # a leads gravou
        avisos = " ".join(str(n) for n in cur.connection.notices)
        assert "lead_utm: falha ao registrar o histórico" in avisos      # e o problema ficou visível
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT quebra")


def test_lote_grande_grava_tudo_e_custa_pouco(cur):
    """20 mil contatos em UM comando: o trigger faz uma inserção em lote, não uma por linha."""
    cur.execute(f"CREATE TABLE zz_leads_sem (LIKE {N.leads} INCLUDING ALL)")
    sql = """INSERT INTO {t} (id, email, utm_source, utm_medium, utm_campaign, utm_content, utm_term)
             SELECT 'lote' || g, 'lote' || g || '@teste.com', 'facebook', 'cpc',
                    '[MA][captação][quente][PI-AGO-26][20.07.26]', 'AD' || (g % 50), ''
             FROM generate_series(1, 20000) g
             ON CONFLICT (id) DO UPDATE SET utm_campaign = EXCLUDED.utm_campaign"""
    t0 = time.time(); cur.execute(sql.format(t="zz_leads_sem")); sem = time.time() - t0
    t0 = time.time(); cur.execute(sql.format(t=N.leads)); com = time.time() - t0
    cur.execute(f"SELECT count(*) FROM {N.estado} WHERE contact_id LIKE 'lote%'")
    assert cur.fetchone()[0] == 20000
    print(f"\n20.000 contatos: sem trigger {sem:.2f}s | com trigger {com:.2f}s | custo {com - sem:.2f}s")
    assert com < 60


def test_regex_do_codigo_igual_ao_do_python(cur):
    """A regra "esta UTM nomeia um lançamento" existe em SQL e em Python: não podem divergir."""
    from etl_active_campaign import extract_launch_code  # noqa: PLC0415

    fixas = [PI, PI2, BF, BV, "pi-jan-26", "PBB-AGO-26", "[base-forte-bv-26]", "XPI-AGO-26",
             "pi_ago_26", "link_bio", "{{campaign.name}}", "", "organico", "bv-25",
             "[MA][PI-AGO-26] e [PES-SET-26]", "pes-mai-26-remarketing", "AGO-26", "PI-AGO-2"]
    cur.execute("SELECT DISTINCT utm_campaign FROM lead_utm_lancamento TABLESAMPLE SYSTEM (1) LIMIT 4000")
    amostra = [r[0] for r in cur.fetchall()]
    nomes = list(dict.fromkeys(fixas + amostra))
    cur.execute("SELECT s, upper((regexp_match(s, %s, 'i'))[1]) FROM unnest(%s::text[]) s",
                (ht.REGEX_CODIGO, nomes))
    divergentes = [(s, sql, extract_launch_code(s)) for s, sql in cur.fetchall()
                   if (sql or None) != extract_launch_code(s)]
    assert not divergentes, f"{len(divergentes)} divergências, ex.: {divergentes[:5]}"


# ── a visão `leads_por_lancamento` ────────────────────────────────────────────

def _visao(c, cid):
    c.execute(f"SELECT lancamento_codigo, utm_content FROM {N.visao} WHERE id = %s ORDER BY 1", (cid,))
    return c.fetchall()


def test_visao_devolve_o_contato_sob_cada_lancamento_com_a_utm_daquele_lancamento(cur):
    """O caso que motivou tudo: a `leads` já aponta para a Black, mas o PI-AGO-26 continua achando a pessoa."""
    _upsert(cur, "v1", PI, content="AD100")
    cur.execute(f"UPDATE {N.leads} SET lancamento_codigo = 'PI-AGO-26' WHERE id = 'v1'")
    _upsert(cur, "v1", BF, content="AD-BF01")
    cur.execute(f"UPDATE {N.leads} SET lancamento_codigo = 'BV-26' WHERE id = 'v1'")
    cur.execute(f"SELECT count(*) FROM {N.leads} WHERE id = 'v1' AND lancamento_codigo = 'PI-AGO-26'")
    assert cur.fetchone()[0] == 0                                   # a leads sozinha já perdeu
    assert _visao(cur, "v1") == [("BV-26", "AD-BF01"), ("PI-AGO-26", "AD100")]   # a visão recupera


def test_visao_mantem_contato_que_so_a_leads_marca_com_o_lancamento(cur):
    """Código vindo do fallback por pasta (sem UTM que o nomeie): comportamento antigo preservado."""
    cur.execute(f"""INSERT INTO {N.leads} (id, email, utm_campaign, utm_content, lancamento_codigo)
                    VALUES ('v2', 'v2@teste.com', 'link_bio', 'AD777', 'PBB-JUN-26')""")
    assert _visao(cur, "v2") == [("PBB-JUN-26", "AD777")]


def test_visao_nunca_devolve_menos_do_que_a_leads(cur):
    """Para qualquer lançamento: contatos da visão >= contatos de `leads WHERE lancamento_codigo = X`."""
    for i in range(30):
        _upsert(cur, f"s{i}", PI, content=f"AD{i}")
        cur.execute(f"UPDATE {N.leads} SET lancamento_codigo = 'PI-AGO-26' WHERE id = %s", (f"s{i}",))
    for i in range(10):                                              # 10 deles migram para a Black
        _upsert(cur, f"s{i}", BF, content="AD-BF01")
        cur.execute(f"UPDATE {N.leads} SET lancamento_codigo = 'BV-26' WHERE id = %s", (f"s{i}",))
    for cod in ("PI-AGO-26", "BV-26"):
        cur.execute(f"SELECT count(*) FROM {N.leads} WHERE lancamento_codigo = %s AND id LIKE 's%%'", (cod,))
        antes = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {N.visao} WHERE lancamento_codigo = %s AND id LIKE 's%%'", (cod,))
        assert cur.fetchone()[0] >= antes
    cur.execute(f"SELECT count(*) FROM {N.visao} WHERE lancamento_codigo = 'PI-AGO-26' AND id LIKE 's%%'")
    assert cur.fetchone()[0] == 30                                   # os 10 que saíram voltaram


def test_visao_devolve_uma_linha_por_contato_e_lancamento_na_black(cur):
    """Base Forte e Vitalícia são o mesmo BV-26: nenhum contato pode contar em dobro."""
    _upsert(cur, "v3", BF, content="AD-BF01")
    _upsert(cur, "v3", BV, content="AD-BV07")
    _upsert(cur, "v4", BF, content="AD-BF02")
    assert _visao(cur, "v3") == [("BV-26", "AD-BV07")]               # a da Vitalícia, a oferta vendida
    assert _visao(cur, "v4") == [("BV-26", "AD-BF02")]               # só Base Forte: cai nela
    cur.execute(f"SELECT count(*) FROM {N.visao} WHERE id IN ('v3', 'v4') AND lancamento_codigo = 'BV-26'")
    assert cur.fetchone()[0] == 2


def test_visao_tem_exatamente_as_colunas_da_leads(cur):
    """É o que permite trocar `FROM leads` por `FROM leads_por_lancamento` sem mexer no resto da consulta."""
    cur.execute(f"SELECT * FROM {N.leads} LIMIT 0")
    da_leads = [d[0] for d in cur.description]
    cur.execute(f"SELECT * FROM {N.visao} LIMIT 0")
    assert [d[0] for d in cur.description] == da_leads


def test_reverter_a_visao_devolve_o_comportamento_antigo(cur):
    _upsert(cur, "v5", PI, content="AD100")
    cur.execute(f"UPDATE {N.leads} SET lancamento_codigo = 'PI-AGO-26' WHERE id = 'v5'")
    _upsert(cur, "v5", BF, content="AD-BF01")
    cur.execute(f"UPDATE {N.leads} SET lancamento_codigo = 'BV-26' WHERE id = 'v5'")
    cur.execute("SAVEPOINT reverte")
    try:
        cur.execute(ht.ddl_visao_reverter(N))
        assert _visao(cur, "v5") == [("BV-26", "AD-BF01")]           # só o que a leads tem, como antes
    finally:
        cur.execute("ROLLBACK TO SAVEPOINT reverte")
