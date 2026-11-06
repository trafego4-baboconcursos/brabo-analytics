"""Área Comercial — Regras e vendedores, metas e bônus (Task 7a). Sem banco: um FakeBanco que
entende SÓ as declarações exatas do módulo (qualquer outro SQL estoura) e volta atrás na
transação que levanta exceção, então rotas e escritas rodam de verdade sobre ele.
"""
import os

os.environ["PRE_WARM_CACHE"] = "false"
os.environ.setdefault("SECRET_KEY", "smoke-secret-key-para-testes")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")
os.environ.setdefault("SUPABASE_USERS_URL", "postgresql://smoke:smoke@127.0.0.1:1/smoke")

import copy  # noqa: E402
from datetime import date, datetime  # noqa: E402
from decimal import Decimal as D  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

import frontend.db_readers.comercial as com  # noqa: E402
from frontend.services.comercial import acesso as acesso_mod  # noqa: E402
from frontend.services.comercial import regras_tela as rt  # noqa: E402
from frontend.services.comercial import snapshot as snap  # noqa: E402
from frontend.services.comercial import telas  # noqa: E402
from frontend.services.comercial.acesso import AcessoComercial  # noqa: E402
from frontend.services.comercial.calculo import LinhaComissao  # noqa: E402
from frontend.services.comercial.snapshot import ResultadoMes  # noqa: E402


def _n(sql: str) -> str:
    return " ".join(str(sql).split())


class _Res:
    def __init__(self, rows=(), rowcount=0):
        self._rows, self.rowcount = list(rows), rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


# ---------------------------------------------------------------- FakeBanco
class FakeBanco:
    """comercial_* em memória + launch_config (só leitura). Só as declarações exatas."""

    def __init__(self):
        self.vend = {"AT4": {"nome": "Ediléia", "ativo": True, "criado_auto": False},
                     "AT9": {"nome": "Jheniffer", "ativo": True, "criado_auto": False},
                     "AT6": {"nome": "Vendedor 6", "ativo": True, "criado_auto": True},
                     "AT12": {"nome": "Rafael Batista", "ativo": False, "criado_auto": False}}
        self.acessos = {"master@teste.local": ("master", None), "coord@teste.local": ("coordenador", None),
                        "edileia@teste.local": ("vendedor", "AT4")}
        self.regras = [
            {"id": 1, "plataforma": "hotmart", "modalidade": "cartao_pix", "tipo": "Ativa", "pct": D("0.04"),
             "vendedor_codigo": None, "vigente_de": date(2026, 1, 1), "vigente_ate": None,
             "categorias": None, "forca_tipo": None},
            {"id": 2, "plataforma": "hotmart", "modalidade": "parcelado", "tipo": "Ativa", "pct": D("0.04"),
             "vendedor_codigo": None, "vigente_de": date(2026, 1, 1), "vigente_ate": date(2026, 9, 30),
             "categorias": None, "forca_tipo": None},
            {"id": 3, "plataforma": "hotmart", "modalidade": "parcelado", "tipo": "Ativa", "pct": D("0.02"),
             "vendedor_codigo": None, "vigente_de": date(2026, 10, 1), "vigente_ate": None,
             "categorias": None, "forca_tipo": None},
            {"id": 4, "plataforma": "tmb", "modalidade": "parcelado", "tipo": "Ativa", "pct": D("0.04"),
             "vendedor_codigo": "AT9", "vigente_de": date(2026, 1, 1), "vigente_ate": date(2026, 10, 31),
             "categorias": ["CROSS SELL", "UP SELL"], "forca_tipo": "Ativa"},
        ]
        self.parts = [{"id": 1, "beneficiario": "Rafael Batista", "pct_ativa": D("0.003"), "pct_reativa": D("0.001"),
                       "vigente_de": date(2026, 1, 1), "vigente_ate": None, "beneficiario_codigo": "AT12"}]
        self.bases = [{"id": 1, "plataforma": "hotmart", "valor_cobrado": D("89.90"), "valor_base": D("1477"),
                       "categoria": "LEAD", "vigente_de": date(2026, 1, 1), "vigente_ate": None},
                      {"id": 2, "plataforma": "hotmart", "valor_cobrado": D("1726"), "valor_base": D("1726"),
                       "categoria": "LEAD", "vigente_de": date(2026, 1, 1), "vigente_ate": None},
                      {"id": 3, "plataforma": "hotmart", "valor_cobrado": D("446"), "valor_base": D("446"),
                       "categoria": "UP SELL", "vigente_de": date(2026, 1, 1), "vigente_ate": None}]
        self.ofertas = {"abc123": {"nome": "COM. LEAD - AT9", "codigo_at": "AT9", "origem": "planilha"}}
        self.janelas = {}
        self.metas = {}
        self.bonus = {}
        self.historico = []
        self.lancamentos = [("PES-NOV-26", "2026-11-16", None, ["111"], []),
                            ("PI-NOV-26", None, None, ["222"], []),
                            ("PBB-OUT-26", None, "2026-10-05", ["333"], [])]
        self.sql: list[str] = []
        self._pilha = []
        h = {
            com.SQL_VEND_LER_UM: lambda p: _Res([(v["nome"], v["ativo"])] if (v := self.vend.get(p["codigo"])) else []),
            com.SQL_VEND_TODOS: lambda p: _Res([(c, v["nome"], v["ativo"], v["criado_auto"]) for c, v in self.vend.items()]),
            com.SQL_VENDEDORES_LISTA: lambda p: _Res(sorted(((c, v["nome"]) for c, v in self.vend.items() if v["ativo"]),
                                                            key=lambda t: t[1])),
            com.SQL_VEND_CRIAR: self._vend_criar,
            com.SQL_VEND_RENOMEAR: lambda p: self._vend_set(p, "nome", p["nome"]),
            com.SQL_VEND_ATIVAR: lambda p: self._vend_set(p, "ativo", True),
            com.SQL_VEND_DESATIVAR: lambda p: self._vend_set(p, "ativo", False),
            com.SQL_ACESSO_LER_UM: lambda p: _Res([self.acessos[p["email"]]] if p["email"] in self.acessos else []),
            com.SQL_ACESSOS_TODOS: lambda p: _Res([(e, n, c, "carga", datetime(2026, 11, 6, 9))
                                                   for e, (n, c) in sorted(self.acessos.items())]),
            com.SQL_ACESSO_UPSERT: self._acesso_upsert,
            com.SQL_ACESSO_REMOVER: self._acesso_remover,
            com.SQL_REGRAS_TODAS: lambda p: _Res([self._tupla(r, com._COLS_REGRA) for r in self.regras]),
            com.SQL_REGRA_LER_UM: lambda p: _Res([self._tupla(r, com._COLS_REGRA) for r in self.regras if r["id"] == p["id"]]),
            com.SQL_REGRA_FECHAR: lambda p: self._fechar(self.regras, p),
            com.SQL_REGRA_INSERIR: self._regra_inserir,
            com.SQL_PARTS_TODAS: lambda p: _Res([self._tupla(r, com._COLS_PART) for r in self.parts]),
            com.SQL_PART_LER_UM: lambda p: _Res([self._tupla(r, com._COLS_PART) for r in self.parts if r["id"] == p["id"]]),
            com.SQL_PART_FECHAR: lambda p: self._fechar(self.parts, p),
            com.SQL_PART_INSERIR: self._part_inserir,
            com.SQL_BASES_TODAS: lambda p: _Res([self._tupla(r, com._COLS_BASE) for r in self.bases]),
            com.SQL_BASE_LER_UM: lambda p: _Res([self._tupla(r, com._COLS_BASE) for r in self.bases if r["id"] == p["id"]]),
            com.SQL_BASES_DA_CHAVE: lambda p: _Res([self._tupla(r, com._COLS_BASE) for r in self.bases
                                                    if r["plataforma"] == p["plataforma"]
                                                    and r["valor_cobrado"] == p["valor_cobrado"]]),
            com.SQL_BASE_FECHAR: lambda p: self._fechar(self.bases, p),
            com.SQL_BASE_INSERIR: self._base_inserir,
            com.SQL_CATEGORIAS_BASE: lambda p: _Res([(c,) for c in {b["categoria"] for b in self.bases}]),
            com.SQL_OFERTA_LER_UM: lambda p: _Res([(o["nome"], o["codigo_at"])] if (o := self.ofertas.get(p["codigo_do_preco"])) else []),
            com.SQL_OFERTAS_TODAS: lambda p: _Res([(k, o["nome"], o["codigo_at"], o["origem"]) for k, o in sorted(self.ofertas.items())]),
            com.SQL_OFERTA_UPSERT: self._oferta_upsert,
            com._SQL_JANELAS: lambda p: _Res(self.lancamentos),
            com.SQL_JANELAS_MANUAIS: lambda p: _Res([(k, j["inicio"], j["fim"], j["por"], datetime(2026, 11, 6, 9))
                                                     for k, j in self.janelas.items()]),
            com.SQL_JANELA_LER_UM: lambda p: _Res([(j["inicio"], j["fim"])] if (j := self.janelas.get(p["lancamento"])) else []),
            com.SQL_JANELA_UPSERT: self._janela_upsert,
            com.SQL_JANELA_REMOVER: lambda p: _Res(rowcount=1 if self.janelas.pop(p["lancamento"], None) else 0),
            com.SQL_META_LER_UM: lambda p: _Res([(m["valor"],)] if (m := self.metas.get((p["vendedor_codigo"], p["mes"]))) else []),
            com.SQL_META_UPSERT: lambda p: self._upsert(self.metas, p),
            com.SQL_METAS_DO_MES: lambda p: _Res(self._do_mes(self.metas, p)),
            com.SQL_METAS_DO_VENDEDOR: lambda p: _Res(self._do_mes(self.metas, p, p["codigo"])),
            com.SQL_BONUS_LER_UM: lambda p: _Res([(b["valor"], b["justificativa"])] if (b := self.bonus.get((p["vendedor_codigo"], p["mes"]))) else []),
            com.SQL_BONUS_UPSERT: lambda p: self._upsert(self.bonus, p),
            com.SQL_BONUS_DO_MES: lambda p: _Res(self._do_mes(self.bonus, p, bonus=True)),
            com.SQL_BONUS_DO_VENDEDOR: lambda p: _Res(self._do_mes(self.bonus, p, p["codigo"], bonus=True)),
            com.SQL_HISTORICO_INSERIR: self._hist,
            com.SQL_HISTORICO_100: lambda p: _Res([(h["tabela"], h["registro_id"], h["campo"], h["antes"], h["depois"],
                                                    h["por"], datetime(2026, 11, 6, 10)) for h in reversed(self.historico)]),
        }
        self.h = {_n(k): v for k, v in h.items()}

    # ---- conexão (com volta atrás na exceção, como o engine.begin())
    def execute(self, stmt, params=None):
        s = _n(stmt)
        self.sql.append(s)
        if s not in self.h:
            raise AssertionError(f"SQL fora do esperado: {s[:140]}")
        return self.h[s](params or {})

    def connect(self):
        return self

    begin = connect

    _ESTADO = ("vend", "acessos", "regras", "parts", "bases", "ofertas", "janelas", "metas", "bonus", "historico")

    def __enter__(self):
        self._pilha.append({k: copy.deepcopy(getattr(self, k)) for k in self._ESTADO})
        return self

    def __exit__(self, tipo, *a):
        estado = self._pilha.pop()
        if tipo is not None:
            for k, v in estado.items():
                setattr(self, k, v)
        return False

    def escritas(self):
        return [s for s in self.sql if not s.startswith("SELECT")]

    # ---- handlers
    @staticmethod
    def _tupla(r, cols):
        return tuple(r[c] for c in cols)

    def _vend_criar(self, p):
        if p["codigo"] in self.vend:
            return _Res(rowcount=0)
        self.vend[p["codigo"]] = {"nome": p["nome"], "ativo": True, "criado_auto": False}
        return _Res(rowcount=1)

    def _vend_set(self, p, campo, valor):
        if p["codigo"] not in self.vend:
            return _Res(rowcount=0)
        self.vend[p["codigo"]][campo] = valor
        return _Res(rowcount=1)

    def _acesso_upsert(self, p):
        assert p["email"] == p["email"].strip().lower()
        self.acessos[p["email"]] = (p["nivel"], p["vendedor_codigo"])
        return _Res(rowcount=1)

    def _acesso_remover(self, p):
        return _Res(rowcount=1 if self.acessos.pop(p["email"], None) else 0)

    @staticmethod
    def _fechar(tabela, p):
        for r in tabela:
            if r["id"] == p["id"] and r["vigente_ate"] is None and r["vigente_de"] <= p["vigente_ate"]:
                r["vigente_ate"] = p["vigente_ate"]
                return _Res(rowcount=1)
        return _Res(rowcount=0)

    def _novo_id(self, tabela):
        return max((r["id"] for r in tabela), default=0) + 1

    def _regra_inserir(self, p):
        assert p["categorias"] is None or p["categorias"] == sorted(p["categorias"])
        chave = com.chave_regra(p) + (p["vigente_de"],)
        if any(com.chave_regra(r) + (r["vigente_de"],) == chave for r in self.regras):
            raise IntegrityError("INSERT", {}, Exception("ux_comercial_regras_nat"))
        self.regras.append({**{c: p.get(c) for c in com._COLS_REGRA if c != "id"}, "id": self._novo_id(self.regras),
                            "vigente_ate": None})
        return _Res(rowcount=1)

    def _part_inserir(self, p):
        if any((r["beneficiario"], r["vigente_de"]) == (p["beneficiario"], p["vigente_de"]) for r in self.parts):
            raise IntegrityError("INSERT", {}, Exception("ux_comercial_participacoes_nat"))
        self.parts.append({**{c: p.get(c) for c in com._COLS_PART if c != "id"}, "id": self._novo_id(self.parts),
                           "vigente_ate": None})
        return _Res(rowcount=1)

    def _base_inserir(self, p):
        if any((r["plataforma"], r["valor_cobrado"], r["vigente_de"]) == (p["plataforma"], p["valor_cobrado"], p["vigente_de"])
               for r in self.bases):
            raise IntegrityError("INSERT", {}, Exception("ux_comercial_valores_base_nat"))
        self.bases.append({**{c: p.get(c) for c in com._COLS_BASE if c != "id"}, "id": self._novo_id(self.bases),
                           "vigente_ate": None})
        return _Res(rowcount=1)

    def _oferta_upsert(self, p):
        self.ofertas[p["codigo_do_preco"]] = {"nome": p["nome_deste_preco"], "codigo_at": p["codigo_at"], "origem": "tela"}
        return _Res(rowcount=1)

    def _janela_upsert(self, p):
        assert p["fim"] > p["inicio"]
        self.janelas[p["lancamento"]] = {"inicio": p["inicio"], "fim": p["fim"], "por": p["por"]}
        return _Res(rowcount=1)

    @staticmethod
    def _upsert(tab, p):
        assert p["valor"] >= 0
        tab[(p["vendedor_codigo"], p["mes"])] = dict(p)
        return _Res(rowcount=1)

    def _do_mes(self, tab, p, codigo=None, bonus=False):
        out = []
        for (cod, mes), v in tab.items():
            if mes != p["mes"] or (codigo and cod != codigo):
                continue
            nome = (self.vend.get(cod) or {}).get("nome")
            out.append((cod, v["valor"], nome, v.get("justificativa")) if bonus else (cod, v["valor"], nome))
        return out

    def _hist(self, p):
        self.historico.append(dict(p))
        return _Res(rowcount=1)


@pytest.fixture
def banco(monkeypatch):
    b = FakeBanco()
    monkeypatch.setattr(com, "_get_users_engine", lambda: b)
    return b


# ---------------------------------------------------------------- guarda
def test_escritas_da_tela_de_regras_passam_na_guarda():
    for sql in com.ESCRITAS_REGRAS:
        com.exigir_so_comercial(sql)
    for d in com.DDL:
        com.exigir_so_comercial(d)


@pytest.mark.parametrize("quase", [
    # versionar sem a trava "ainda aberta": reabriria/encurtaria linha encerrada
    "UPDATE comercial_regras_percentual SET vigente_ate = :vigente_ate WHERE id = :id",
    # editar o valor no lugar (Ruling 15 proíbe)
    "UPDATE comercial_regras_percentual SET pct = :pct WHERE id = :id",
    "UPDATE comercial_valores_base SET valor_base = :valor_base WHERE id = :id",
    # sem WHERE
    "UPDATE comercial_vendedores SET nome = :nome",
    "UPDATE comercial_vendedores SET ativo = false",
    "DELETE FROM comercial_acessos",
    # mesma forma em tabela fora da área
    "DELETE FROM users WHERE email = :email",
    "DELETE FROM launch_config WHERE lancamento = :lancamento",
    "DELETE FROM comercial_vendedores WHERE codigo = :codigo",
    com.SQL_ACESSO_UPSERT.replace("comercial_acessos", "users"),
    com.SQL_BONUS_UPSERT + "; DROP TABLE comercial_historico",
    com.SQL_ACESSO_REMOVER + " OR true",
    com.SQL_PART_FECHAR.replace(" AND vigente_ate IS NULL", ""),
])
def test_quase_copias_sao_recusadas(quase):
    with pytest.raises(RuntimeError, match="recusou"):
        com.exigir_so_comercial(quase)


def test_ddl_tabelas_novas():
    cols = com.colunas_do_ddl()
    assert cols["comercial_janela_reativa"] == {"lancamento": "text", "inicio": "timestamp without time zone",
                                                "fim": "timestamp without time zone", "criado_por": "text",
                                                "criado_em": "timestamp with time zone"}
    assert set(cols["comercial_metas"]) == {"vendedor_codigo", "mes", "valor", "criado_por", "criado_em"}
    assert set(cols["comercial_bonus"]) == {"vendedor_codigo", "mes", "valor", "justificativa", "criado_por",
                                            "criado_em"}
    assert any("comercial_metas" in d and "CHECK (valor >= 0)" in d and "PRIMARY KEY (vendedor_codigo, mes)" in d
               for d in com.DDL)


def test_escritas_passam_pela_guarda_ao_executar(banco, monkeypatch):
    vistas = []
    original = com.exigir_so_comercial
    monkeypatch.setattr(com, "exigir_so_comercial", lambda s: (vistas.append(_n(s)), original(s)))
    com.criar_vendedor("AT20", "Nova", "g@x")
    com.renomear_vendedor("AT20", "Nova Silva", "g@x")
    com.definir_vendedor_ativo("AT20", False, "g@x")
    com.gravar_acesso("nova@x", "vendedor", "AT4", "g@x")
    com.remover_acesso("nova@x", "g@x")
    com.nova_versao_regra(1, D("0.05"), date(2026, 11, 1), "g@x")
    com.nova_regra("tmb", "parcelado", "Reativa", D("0.01"), "AT4", ["LEAD"], None, date(2026, 11, 1), "g@x")
    com.encerrar_regra(3, date(2026, 12, 1), "g@x")
    com.nova_versao_participacao(1, D("0.004"), D("0.002"), date(2026, 11, 1), "g@x")
    com.nova_versao_base(1, D("1500"), "LEAD", date(2026, 11, 1), "g@x")
    com.nova_base("tmb", D("99"), D("1879.34"), "LEAD", date(2026, 11, 1), "g@x")
    com.gravar_oferta("xyz", "COM. UP - AT4", "g@x")
    com.gravar_janela("PI-NOV-26", datetime(2026, 11, 9), datetime(2026, 11, 17, 23, 59, 59), "g@x")
    com.remover_janela("PI-NOV-26", "g@x")
    com.gravar_meta("AT4", date(2026, 11, 1), D("50000"), "g@x")
    com.gravar_bonus("AT4", date(2026, 11, 1), D("300"), "campanha", "g@x")
    assert banco.escritas() == vistas  # nenhuma escrita sem passar pela guarda
    assert set(vistas) <= {_n(q) for q in (*com.ESCRITAS_REGRAS, com.SQL_HISTORICO_INSERIR)}
    assert len(banco.historico) == 16  # uma linha de histórico por escrita


# ---------------------------------------------------------------- versionamento (Ruling 15)
def test_nova_versao_de_percentual_fecha_e_abre(banco):
    com.nova_versao_regra(1, D("0.05"), date(2026, 11, 1), "g@x")
    velha, nova = banco.regras[0], banco.regras[-1]
    assert (velha["pct"], velha["vigente_de"], velha["vigente_ate"]) == (D("0.04"), date(2026, 1, 1), date(2026, 10, 31))
    assert (nova["pct"], nova["vigente_de"], nova["vigente_ate"]) == (D("0.05"), date(2026, 11, 1), None)
    assert com.chave_regra(nova) == com.chave_regra(velha)
    h = banco.historico[-1]
    assert (h["tabela"], h["campo"], h["por"]) == ("comercial_regras_percentual", "pct", "g@x")
    assert h["antes"].startswith("0.04 (de 2026-01-01, agora até 2026-10-31)")
    assert h["depois"] == "0.05 (a partir de 2026-11-01)"
    # o motor usa a velha em outubro e a nova em novembro
    from frontend.services.comercial.tabelas import escolher_percentual
    regras = [com._regra_da_linha(tuple(r[c] for c in com._COLS_REGRA)) for r in banco.regras]
    assert escolher_percentual(regras, "hotmart", "cartao_pix", "Ativa", "AT4", date(2026, 10, 20)).pct == D("0.04")
    assert escolher_percentual(regras, "hotmart", "cartao_pix", "Ativa", "AT4", date(2026, 11, 2)).pct == D("0.05")


def test_versao_preserva_categorias_e_forca_tipo(banco):
    banco.regras[3]["vigente_ate"] = None
    com.nova_versao_regra(4, D("0.03"), date(2026, 11, 1), "g@x")
    nova = banco.regras[-1]
    assert (nova["categorias"], nova["forca_tipo"], nova["vendedor_codigo"]) == (["CROSS SELL", "UP SELL"], "Ativa", "AT9")


@pytest.mark.parametrize("id_,de,codigo", [
    (1, date(2026, 1, 1), "versao_data"),       # não começa depois da vigente
    (2, date(2026, 11, 1), "versao_encerrada"),  # linha já encerrada
    (99, date(2026, 11, 1), "nao_encontrada"),
])
def test_versao_recusada(banco, id_, de, codigo):
    antes = copy.deepcopy(banco.regras)
    with pytest.raises(com.EscritaRecusada) as e:
        com.nova_versao_regra(id_, D("0.05"), de, "g@x")
    assert e.value.codigo == codigo
    assert banco.regras == antes and banco.historico == []


def test_nova_regra_categorias_ordenadas_e_chave_livre(banco):
    com.nova_regra("hotmart", "cartao_pix", "Ativa", D("0.05"), "AT4", ["UP SELL", "CROSS SELL", "UP SELL"], "Ativa",
                   date(2026, 11, 1), "g@x")
    assert banco.regras[-1]["categorias"] == ["CROSS SELL", "UP SELL"]
    # mesma chave (categorias em outra ordem) já aberta -> recusa
    with pytest.raises(com.EscritaRecusada) as e:
        com.nova_regra("hotmart", "cartao_pix", "Ativa", D("0.06"), "AT4", ["CROSS SELL", "UP SELL"], None,
                       date(2026, 12, 1), "g@x")
    assert e.value.codigo == "ja_existe_aberta"
    # regra do time aberta (id 1) -> use Nova versão
    with pytest.raises(com.EscritaRecusada) as e:
        com.nova_regra("hotmart", "cartao_pix", "Ativa", D("0.06"), None, None, None, date(2026, 12, 1), "g@x")
    assert e.value.codigo == "ja_existe_aberta"


def test_nova_regra_nao_sobrepoe_vigencia_encerrada(banco):
    # AT9 TMB parcelado Ativa (cross/up) encerrada em 31/10: começar em 01/10 mudaria outubro
    with pytest.raises(com.EscritaRecusada) as e:
        com.nova_regra("tmb", "parcelado", "Ativa", D("0.05"), "AT9", ["UP SELL", "CROSS SELL"], None,
                       date(2026, 10, 1), "g@x")
    assert e.value.codigo == "sobrepoe_vigencia"
    com.nova_regra("tmb", "parcelado", "Ativa", D("0.05"), "AT9", ["UP SELL", "CROSS SELL"], None,
                   date(2026, 11, 1), "g@x")


def test_nova_regra_de_vendedor_inexistente(banco):
    with pytest.raises(com.EscritaRecusada) as e:
        com.nova_regra("tmb", "parcelado", "Ativa", D("0.05"), "AT77", None, None, date(2026, 11, 1), "g@x")
    assert e.value.codigo == "vendedor_nao_encontrado"


def test_insercao_duplicada_volta_tudo(banco, monkeypatch):
    # corrida: a leitura não viu, o índice único barra -> nada gravado, nem o fechamento
    monkeypatch.setattr(com, "_conferir_chave_livre", lambda linhas, de: None)
    with pytest.raises(com.EscritaRecusada) as e:
        com.nova_regra("hotmart", "cartao_pix", "Ativa", D("0.06"), None, None, None, date(2026, 1, 1), "g@x")
    assert e.value.codigo == "duplicado"
    assert len(banco.regras) == 4 and banco.historico == []


def test_encerrar_regra(banco):
    com.encerrar_regra(1, date(2026, 12, 1), "g@x")
    assert banco.regras[0]["vigente_ate"] == date(2026, 11, 30) and len(banco.regras) == 4
    assert (banco.historico[-1]["antes"], banco.historico[-1]["depois"]) == ("aberta", "2026-11-30")


def test_participacao_versao_e_nova(banco):
    com.nova_versao_participacao(1, D("0.004"), D("0.0015"), date(2026, 11, 1), "g@x")
    assert banco.parts[0]["vigente_ate"] == date(2026, 10, 31)
    nova = banco.parts[-1]
    assert (nova["pct_ativa"], nova["pct_reativa"], nova["beneficiario_codigo"]) == (D("0.004"), D("0.0015"), "AT12")
    with pytest.raises(com.EscritaRecusada) as e:
        com.nova_participacao("rafael batista", None, D("0.01"), D("0.01"), date(2026, 12, 1), "g@x")
    assert e.value.codigo == "ja_existe_aberta"
    com.nova_participacao("Rafael Lago", None, D("0.002"), D("0.001"), date(2026, 11, 1), "g@x")
    assert banco.parts[-1]["beneficiario"] == "Rafael Lago"
    com.encerrar_participacao(3, date(2026, 12, 1), "g@x")
    assert banco.parts[-1]["vigente_ate"] == date(2026, 11, 30)


def test_valor_base_versao_e_nova(banco):
    com.nova_versao_base(1, D("1500"), "LEAD", date(2026, 11, 1), "g@x")
    assert banco.bases[0]["vigente_ate"] == date(2026, 10, 31)
    assert (banco.bases[-1]["valor_cobrado"], banco.bases[-1]["valor_base"]) == (D("89.90"), D("1500"))
    with pytest.raises(com.EscritaRecusada) as e:
        com.nova_base("hotmart", D("1726"), D("1700"), "LEAD", date(2026, 11, 1), "g@x")
    assert e.value.codigo == "ja_existe_aberta"
    com.nova_base("hotmart", D("12.34"), D("1477"), "LEAD", date(2026, 10, 1), "g@x")
    assert banco.bases[-1]["valor_cobrado"] == D("12.34")


# ---------------------------------------------------------------- vendedores, acessos, ofertas, janela
def test_vendedores(banco):
    with pytest.raises(com.EscritaRecusada) as e:
        com.criar_vendedor("AT4", "Outra", "g@x")
    assert e.value.codigo == "vendedor_existe"
    com.renomear_vendedor("AT6", "Bruna", "g@x")
    assert banco.vend["AT6"]["nome"] == "Bruna"
    assert (banco.historico[-1]["antes"], banco.historico[-1]["depois"]) == ("Vendedor 6", "Bruna")
    with pytest.raises(com.EscritaRecusada) as e:
        com.definir_vendedor_ativo("AT4", True, "g@x")
    assert e.value.codigo == "sem_mudanca"
    com.definir_vendedor_ativo("AT12", True, "g@x")
    assert banco.vend["AT12"]["ativo"] is True


def test_acessos(banco):
    com.gravar_acesso("pri@teste.local", "vendedor", "AT9", "g@x")
    assert banco.acessos["pri@teste.local"] == ("vendedor", "AT9")
    with pytest.raises(com.EscritaRecusada) as e:
        com.gravar_acesso("x@teste.local", "vendedor", "AT77", "g@x")
    assert e.value.codigo == "vendedor_nao_encontrado"
    com.gravar_acesso("pri@teste.local", "coordenador", "AT9", "g@x")  # código some fora de vendedor
    assert banco.acessos["pri@teste.local"] == ("coordenador", None)
    assert banco.historico[-1]["antes"] == "vendedor (AT9)" and banco.historico[-1]["depois"] == "coordenador"
    com.remover_acesso("pri@teste.local", "g@x")
    assert "pri@teste.local" not in banco.acessos
    with pytest.raises(com.EscritaRecusada):
        com.remover_acesso("pri@teste.local", "g@x")


def test_oferta_extrai_codigo(banco):
    com.gravar_oferta("abc123", "COM. LEAD - AT 04", "g@x")
    assert banco.ofertas["abc123"]["codigo_at"] == "AT4"
    assert banco.historico[-1]["antes"] == "COM. LEAD - AT9"


def test_janela_manual_sobrepoe_e_cobre_sem_data():
    linhas = [("PES-NOV-26", "2026-11-16", None, ["111"], []), ("PI-NOV-26", None, None, ["222"], [])]
    manuais = {"PES-NOV-26": (datetime(2026, 11, 10), datetime(2026, 11, 20, 12)),
               "PI-NOV-26": (datetime(2026, 11, 2), datetime(2026, 11, 9, 23, 59, 59))}
    js, sem = com.janelas_do_periodo(linhas, date(2026, 11, 1), date(2026, 11, 30))
    assert [j.lancamento for j in js] == ["PES-NOV-26"] and [s[0] for s in sem] == ["PI-NOV-26"]
    js, sem = com.janelas_do_periodo(linhas, date(2026, 11, 1), date(2026, 11, 30), manuais=manuais)
    assert sem == []
    por = {j.lancamento: j for j in js}
    assert (por["PES-NOV-26"].inicio, por["PES-NOV-26"].fim) == manuais["PES-NOV-26"]
    assert por["PI-NOV-26"].produtos_hotmart == frozenset({"222"}) and por["PI-NOV-26"].projeto == "INSS"


def test_ler_janelas_usa_a_manual(banco):
    banco.janelas["PI-NOV-26"] = {"inicio": datetime(2026, 11, 2), "fim": datetime(2026, 11, 9, 23, 59, 59), "por": "g"}
    js, sem = com.ler_janelas(date(2026, 11, 1), date(2026, 11, 30))
    assert "PI-NOV-26" in {j.lancamento for j in js}
    assert "PI-NOV-26" not in {s[0] for s in sem}


def test_janela_grava_e_devolve_anterior(banco):
    assert com.gravar_janela("PES-NOV-26", datetime(2026, 11, 10), datetime(2026, 11, 18), "g@x") is None
    antes = com.gravar_janela("PES-NOV-26", datetime(2026, 11, 11), datetime(2026, 11, 18), "g@x")
    assert antes == (datetime(2026, 11, 10), datetime(2026, 11, 18))
    with pytest.raises(com.EscritaRecusada):
        com.gravar_janela("PES-NOV-26", datetime(2026, 11, 11), datetime(2026, 11, 18), "g@x")


# ---------------------------------------------------------------- serviço: entrada pt-BR e validações
@pytest.mark.parametrize("txt,esperado", [("4", D("0.04")), ("4,5", D("0.045")), ("0,75", D("0.0075")),
                                          ("0.3", D("0.003")), ("10%", D("0.1"))])
def test_pct(txt, esperado):
    assert rt.pct(txt) == esperado


@pytest.mark.parametrize("txt,esperado", [("1.477", D("1477.00")), ("1.477,50", D("1477.50")), ("89,90", D("89.90")),
                                          ("R$ 1.879,34", D("1879.34")), ("300", D("300.00"))])
def test_reais(txt, esperado):
    assert rt.reais(txt, "Valor") == esperado


@pytest.mark.parametrize("fn", [lambda: rt.pct(""), lambda: rt.pct("101"), lambda: rt.pct("-1"), lambda: rt.pct("abc"),
                                lambda: rt.reais("0", "V"), lambda: rt.reais("", "V"),
                                lambda: rt.forca_tipo("Reativa", "Ativa"), lambda: rt.email("sem-arroba"),
                                lambda: rt.data_inicio("2025-12-31", date(2026, 11, 6)),
                                lambda: rt.data_inicio("2026-13-01", date(2026, 11, 6)),
                                lambda: rt.janela("2026-11-10T00:00", "2026-11-09T00:00"),
                                lambda: rt.categorias(["NAO EXISTE"], {"LEAD"}),
                                lambda: rt.lancamento("XX-NOV-26", ["PES-NOV-26"]),
                                lambda: rt.mes("2026-12", date(2026, 11, 6)),
                                lambda: rt.conferir_acesso_proprio("a@x", "a@x", None),
                                lambda: rt.conferir_acesso_proprio("a@x", "a@x", "vendedor")])
def test_entrada_invalida(fn):
    with pytest.raises(rt.EntradaInvalida):
        fn()


def test_entrada_valida():
    hoje = date(2026, 11, 6)
    assert rt.data_inicio("", hoje) == date(2026, 11, 1)  # padrão: 1º dia do mês corrente
    assert rt.data_inicio("2026-10-15", hoje) == date(2026, 10, 15)
    assert rt.forca_tipo("", "Ativa") is None and rt.forca_tipo("Ativa", "Ativa") == "Ativa"
    assert rt.email("  Nova@Teste.Local ") == "nova@teste.local"
    assert rt.categorias([], {"LEAD"}) is None
    assert rt.categorias(["UP SELL", "LEAD"], {"LEAD", "UP SELL"}) == ["LEAD", "UP SELL"]
    assert rt.janela("2026-11-09", "2026-11-17") == (datetime(2026, 11, 9), datetime(2026, 11, 17, 23, 59, 59))
    assert rt.mes("2026-12", hoje, ate_proximo=True) == date(2026, 12, 1)
    rt.conferir_acesso_proprio("a@x", "a@x", "coordenador")  # master -> coordenador não tranca ninguém
    assert rt.meses_desde(date(2026, 10, 15), hoje) == [date(2026, 10, 1), date(2026, 11, 1)]
    assert rt.meses_desde(date(2026, 1, 1), hoje) is None  # muitos -> todos
    assert rt.meses_desde(date(2026, 12, 1), hoje) == []
    assert rt.meses_da_janela((datetime(2026, 10, 26), datetime(2026, 11, 3)), None) == [date(2026, 10, 1), date(2026, 11, 1)]


def test_mes_fechado_gancho(monkeypatch):
    monkeypatch.setattr(rt, "_mes_fechado", lambda m: m == date(2026, 10, 1))
    with pytest.raises(rt.EntradaInvalida, match="fechado"):
        rt.data_inicio("2026-10-20", date(2026, 11, 6))
    with pytest.raises(rt.EntradaInvalida, match="fechado"):
        rt.mes("2026-10", date(2026, 11, 6))


def test_grupos_regras_atual_e_historico():
    b = FakeBanco()
    gs = rt.grupos_regras(b.regras)
    par = next(g for g in gs if g["modalidade"] == "parcelado" and not g["vendedor"])
    assert par["atual"]["id"] == 3 and [h["id"] for h in par["historico"]] == [2]
    cat = next(g for g in gs if g["categorias"])
    assert cat["atual"] is None and cat["categorias"] == ["CROSS SELL", "UP SELL"]
    assert gs[-1] is cat  # categoria por último (mais específica)


def test_filtrar_bases():
    b = FakeBanco()
    assert [x["id"] for x in rt.filtrar_bases(b.bases, "1.477")[0]] == [1]
    assert [x["id"] for x in rt.filtrar_bases(b.bases, "89,90")[0]] == [1]
    assert [x["id"] for x in rt.filtrar_bases(b.bases, "up sell")[0]] == [3]
    muitas = [{**b.bases[0], "id": i, "valor_cobrado": D(i)} for i in range(1, 300)]
    ls, total = rt.filtrar_bases(muitas, "")
    assert len(ls) == rt.LIMITE_LISTA and total == 299


# ---------------------------------------------------------------- telas: bônus e meta
MASTER = AcessoComercial("master", None)
COORD = AcessoComercial("coordenador", None)
AT4 = AcessoComercial("vendedor", "AT4")


def _l(tx, cod, base="1000", sit="elegivel"):
    return LinhaComissao(tx, "hotmart", "venda", {"AT4": "Ediléia", "AT9": "Jheniffer"}[cod], cod,
                         datetime(2026, 10, 5, 10), "Ativa", "cartao_pix", "LEAD", D(base), D("0.04"),
                         D(base) * D("0.04") if sit == "elegivel" else D("0"), sit, None, 1, False)


def _linhas():
    return [_l("HP-EDI-1", "AT4", "2000"), _l("HP-JHE-1", "AT9", "5000"), _l("HP-JHE-2", "AT9", "1000")]


def _res():
    return ResultadoMes(date(2026, 10, 1), _linhas(), [], datetime(2026, 11, 6, 9, 42))


BONUS = {"AT4": {"valor": D("150"), "nome": "Ediléia", "justificativa": "campanha"},
         "AT9": {"valor": D("400"), "nome": "Jheniffer", "justificativa": None},
         "AT11": {"valor": D("50"), "nome": "Priscila", "justificativa": None}}
METAS = {"AT4": {"valor": D("4000"), "nome": "Ediléia"}, "AT9": {"valor": D("5000"), "nome": "Jheniffer"},
         "AT11": {"valor": D("1000"), "nome": "Priscila"}}
OUT = telas.resolver_periodo("2026-10", None, None, date(2026, 11, 6))


def test_comissoes_total_a_pagar_soma_bonus():
    v = telas.view_comissoes(_res(), OUT, MASTER, None, BONUS)
    assert v["kpis"]["bonus"] == D("600") and v["kpis"]["total"] == D("320") + D("600")
    por = {r["codigo"]: r for r in v["vendedores"]}
    assert por["AT4"]["a_pagar"] == D("80") + D("150")
    assert por["AT11"]["qtd"] == 0 and por["AT11"]["a_pagar"] == D("50")  # bônus sem venda entra na tabela
    assert v["edita_bonus"] is True


def test_comissoes_vendedor_so_o_proprio_bonus():
    v = telas.view_comissoes(_res(), OUT, AT4, "AT9", BONUS)  # mesmo que o dict venha completo
    assert [r["codigo"] for r in v["vendedores"]] == ["AT4"]
    assert v["kpis"]["bonus"] == D("150") and v["edita_bonus"] is False


def test_comissoes_periodo_livre_sem_bonus():
    livre = telas.resolver_periodo(None, "2026-10-01", "2026-10-31", date(2026, 11, 6), gestor=True)
    assert telas.ler_extras(livre, MASTER) == (None, None)
    v = telas.view_comissoes(_res(), livre, MASTER, None, None)
    assert v["kpis"]["bonus"] is None and v["edita_bonus"] is False


def test_ranking_meta_e_pct():
    rk = telas.ranking(_linhas(), MASTER, "meta", METAS)
    por = {r["codigo"]: r for r in rk["linhas"]}
    assert por["AT9"]["pct_meta"] == D("1.200") and por["AT4"]["pct_meta"] == D("0.500")
    assert por["AT11"]["vendido"] == 0 and por["AT11"]["pct_meta"] == 0
    assert [r["codigo"] for r in rk["linhas"]] == ["AT9", "AT4", "AT11"]


def test_ranking_vendedor_ve_so_a_propria_meta():
    rk = telas.ranking(_linhas(), AT4, "meta", METAS)
    assert rk["ordem"] == "vendido"  # não ordena pelo que não vê
    por = {r["codigo"]: r for r in rk["linhas"]}
    assert por["AT4"]["meta"] == D("4000")
    assert por["AT9"]["meta"] is None and por["AT9"]["pct_meta"] is None
    assert "AT11" not in por


def test_visao_meta_do_time_e_bonus():
    v = telas.view_visao(_res(), OUT, MASTER, BONUS, METAS)
    assert v["meta"] == D("10000") and v["pct_meta"] == D("0.800")
    assert v["kpis"]["total"] == D("320") + D("600")
    v = telas.view_visao(_res(), OUT, AT4, BONUS, METAS)
    assert (v["meta"], v["pct_meta"], v["kpis"]["bonus"]) == (D("4000"), D("0.500"), D("150"))


def test_ler_extras_vendedor_filtra_na_consulta(banco):
    banco.bonus[("AT9", date(2026, 10, 1))] = {"valor": D("400"), "justificativa": None}
    banco.bonus[("AT4", date(2026, 10, 1))] = {"valor": D("150"), "justificativa": "x"}
    bonus, metas = telas.ler_extras(OUT, AT4)
    assert list(bonus) == ["AT4"] and metas == {}
    assert any("AND b.vendedor_codigo = :codigo" in s for s in banco.sql)
    bonus, _ = telas.ler_extras(OUT, MASTER)
    assert set(bonus) == {"AT4", "AT9"}


def test_xlsx_traz_bonus():
    from openpyxl import load_workbook
    import io
    v = telas.view_comissoes(_res(), OUT, MASTER, None, BONUS)
    ws = load_workbook(io.BytesIO(telas.planilha_xlsx(v)))["Resumo"]
    linhas = {r[1]: r for r in ws.iter_rows(min_row=2, values_only=True)}
    assert linhas["AT4"][9] == 150 and linhas["AT4"][10] == 230


# ---------------------------------------------------------------- rotas
_USUARIOS = {"master@teste.local": MASTER, "coord@teste.local": COORD, "edileia@teste.local": AT4}


@pytest.fixture(scope="module")
def _app_client():
    from fastapi.testclient import TestClient

    from frontend.app import app

    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.fixture
def cli(_app_client, banco, monkeypatch):
    import frontend.routes.comercial as rotas

    desat, limpou = [], []
    monkeypatch.setattr(snap, "obter_mes", lambda mes, **kw: _res())
    monkeypatch.setattr(snap, "marcar_desatualizado", lambda mes=None, **kw: desat.append(mes))
    monkeypatch.setattr(rotas, "_hoje", lambda: date(2026, 11, 6))
    monkeypatch.setattr(rotas, "get_launches", lambda: [])
    monkeypatch.setattr(acesso_mod, "acesso_comercial", lambda user, **kw: _USUARIOS.get((user or {}).get("email")))
    monkeypatch.setattr(acesso_mod, "limpar_cache", lambda: limpou.append(1))
    _app_client.desat, _app_client.limpou, _app_client.banco = desat, limpou, banco
    _app_client.cookies.clear()
    return _app_client


def _como(c, email, role="comercial"):
    from frontend.auth import _sign_session
    c.cookies.set("session_token", _sign_session("u-" + email, role, ["PI"], email))
    return c


ROTAS_POST = ["/comercial/regras/vendedores", "/comercial/regras/acessos", "/comercial/regras/percentuais",
              "/comercial/regras/participacoes", "/comercial/regras/bases", "/comercial/regras/ofertas",
              "/comercial/regras/janelas", "/comercial/regras/metas", "/comercial/bonus"]
_FORM = {"acao": "criar", "codigo": "AT30", "nome": "X", "email": "x@teste.local", "nivel": "master",
         "pct": "5", "id": "1", "vigente_de": "2026-11-01", "valor_base": "1", "categoria": "LEAD",
         "codigo_do_preco": "abc", "lancamento": "PES-NOV-26", "inicio": "2026-11-09", "fim": "2026-11-17",
         "vendedor_codigo": "AT4", "mes": "2026-11", "valor": "10", "pct_ativa": "1", "pct_reativa": "1"}


def test_rotas_registradas():
    from frontend.auth import ROUTE_PERMISSIONS, _CMRC_AREA
    for p in ["/comercial/regras", *ROTAS_POST]:
        assert ROUTE_PERMISSIONS[p] == _CMRC_AREA, p


@pytest.mark.parametrize("rota", ROTAS_POST)
@pytest.mark.parametrize("email,role", [("edileia@teste.local", "comercial"), ("ninguem@teste.local", "leitura")])
def test_vendedor_e_sem_nivel_nao_gravam(cli, rota, email, role):
    r = _como(cli, email, role).post(rota, data=_FORM)
    assert r.status_code == 403
    assert cli.banco.escritas() == [] and cli.desat == []


@pytest.mark.parametrize("email,role,status", [("edileia@teste.local", "comercial", 403),
                                               ("ninguem@teste.local", "leitura", 403),
                                               ("coord@teste.local", "comercial", 200)])
def test_pagina_so_gestor(cli, email, role, status):
    assert _como(cli, email, role).get("/comercial/regras").status_code == status


def test_pagina_master(cli):
    cli.banco.janelas["PI-NOV-26"] = {"inicio": datetime(2026, 11, 2), "fim": datetime(2026, 11, 9, 23, 59, 59),
                                      "por": "coord@teste.local"}
    cli.banco.historico.append({"tabela": "comercial_vendedores", "registro_id": "AT6", "campo": "nome",
                                "antes": "Vendedor 6", "depois": "Bruna", "por": "coord@teste.local"})
    html = _como(cli, "master@teste.local").get("/comercial/regras").text
    for trecho in ('id="vendedores"', 'id="acessos"', 'id="percentuais"', 'id="participacoes"',
                   'id="valores-base"', 'id="ofertas"', 'id="janelas"', 'id="metas"', 'id="historico"',
                   "Ediléia", "Vendedor 6", "edileia@teste.local", "Nova versão", "Rafael Batista",
                   "COM. LEAD - AT9", "PES-NOV-26", "PI-NOV-26", "sem data", "precedência sobre as regras específicas",
                   'action="/comercial/regras/percentuais"', 'action="/comercial/regras/metas"',
                   'value="2026-11-01"', "Bruna", 'href="/comercial/regras"'):
        assert trecho in html, trecho
    # o próprio acesso não tem botão de remover
    linha_eu = html.split("master@teste.local")[1].split("</tr>")[0]
    assert "Remover" not in linha_eu


def test_menu_regras_so_para_gestor(cli):
    assert 'href="/comercial/regras"' in _como(cli, "coord@teste.local").get("/comercial/ranking").text
    assert 'href="/comercial/regras"' not in _como(cli, "edileia@teste.local").get("/comercial/ranking").text


def test_versao_de_percentual_pela_rota_invalida_meses(cli):
    r = _como(cli, "coord@teste.local").post("/comercial/regras/percentuais",
                                              data={"acao": "versao", "id": "1", "pct": "4,5", "vigente_de": "2026-10-15"})
    assert r.status_code == 303
    assert r.headers["location"] == "/comercial/regras?ok=regra_versionada#percentuais"
    assert cli.banco.regras[0]["vigente_ate"] == date(2026, 10, 14)
    assert cli.banco.regras[-1]["pct"] == D("0.045")
    assert cli.desat == [date(2026, 10, 1), date(2026, 11, 1)]
    assert cli.banco.historico[-1]["por"] == "coord@teste.local"


def test_versao_sem_data_usa_o_mes_corrente(cli):
    _como(cli, "master@teste.local").post("/comercial/regras/percentuais", data={"acao": "versao", "id": "1", "pct": "5"})
    assert cli.banco.regras[-1]["vigente_de"] == date(2026, 11, 1)
    assert cli.desat == [date(2026, 11, 1)]


def test_versao_recusada_pela_rota(cli):
    r = _como(cli, "master@teste.local").post("/comercial/regras/percentuais",
                                               data={"acao": "versao", "id": "2", "pct": "5"})
    assert r.headers["location"] == "/comercial/regras?erro=versao_encerrada#percentuais"
    assert cli.desat == [] and cli.banco.historico == []
    html = _como(cli, "master@teste.local").get("/comercial/regras?erro=versao_encerrada").text
    assert rt.MENSAGENS_ERRO["versao_encerrada"] in html


def test_nova_regra_forca_tipo_diferente_400(cli):
    r = _como(cli, "master@teste.local").post("/comercial/regras/percentuais", data={
        "acao": "nova", "plataforma": "tmb", "modalidade": "parcelado", "tipo": "Reativa", "pct": "1",
        "forca_tipo": "Ativa", "vigente_de": "2026-11-01"})
    assert r.status_code == 400 and cli.banco.escritas() == []


def test_nova_regra_com_categorias_pela_rota(cli):
    r = _como(cli, "master@teste.local").post("/comercial/regras/percentuais", data={
        "acao": "nova", "plataforma": "tmb", "modalidade": "parcelado", "tipo": "Ativa", "pct": "4",
        "vendedor_codigo": "at4", "categorias": ["UP SELL", "LEAD"], "forca_tipo": "Ativa", "vigente_de": "2026-11-01"})
    assert r.status_code == 303, r.text[:300]
    nova = cli.banco.regras[-1]
    assert (nova["categorias"], nova["vendedor_codigo"], nova["forca_tipo"]) == (["LEAD", "UP SELL"], "AT4", "Ativa")
    r = _como(cli, "master@teste.local").post("/comercial/regras/percentuais", data={
        "acao": "nova", "plataforma": "tmb", "modalidade": "parcelado", "tipo": "Ativa", "pct": "4",
        "categorias": ["INVENTADA"]})
    assert r.status_code == 400


@pytest.mark.parametrize("dados", [
    {"acao": "remover", "email": "MASTER@teste.local"},
    {"acao": "gravar", "email": "master@teste.local", "nivel": "vendedor", "vendedor_codigo": "AT4"},
])
def test_nao_se_tranca_fora(cli, dados):
    r = _como(cli, "master@teste.local").post("/comercial/regras/acessos", data=dados)
    assert r.status_code == 400
    assert cli.banco.escritas() == [] and cli.limpou == []
    assert cli.banco.acessos["master@teste.local"] == ("master", None)


def test_acesso_novo_limpa_cache_e_nao_invalida(cli):
    r = _como(cli, "master@teste.local").post("/comercial/regras/acessos", data={
        "acao": "gravar", "email": " Pri@Teste.Local ", "nivel": "vendedor", "vendedor_codigo": "AT9"})
    assert r.headers["location"] == "/comercial/regras?ok=acesso_gravado#acessos"
    assert cli.banco.acessos["pri@teste.local"] == ("vendedor", "AT9")
    assert cli.limpou == [1] and cli.desat == []
    r = _como(cli, "master@teste.local").post("/comercial/regras/acessos", data={
        "acao": "gravar", "email": "nova@teste.local", "nivel": "vendedor", "vendedor_codigo": "AT77"})
    assert r.headers["location"].endswith("erro=vendedor_nao_encontrado#acessos")


def test_vendedor_renomear_invalida_todos_ativo_nao(cli):
    _como(cli, "master@teste.local").post("/comercial/regras/vendedores",
                                          data={"acao": "renomear", "codigo": "at6", "nome": "  Bruna   Lima "})
    assert cli.banco.vend["AT6"]["nome"] == "Bruna Lima" and cli.desat == [None]
    _como(cli, "master@teste.local").post("/comercial/regras/vendedores", data={"acao": "desativar", "codigo": "AT6"})
    assert cli.banco.vend["AT6"]["ativo"] is False and cli.desat == [None]


def test_janela_pela_rota(cli):
    r = _como(cli, "master@teste.local").post("/comercial/regras/janelas", data={
        "acao": "gravar", "lancamento": "pi-nov-26", "inicio": "2026-10-26T00:00", "fim": "2026-11-03T23:59:59"})
    assert r.status_code == 303
    assert cli.banco.janelas["PI-NOV-26"]["inicio"] == datetime(2026, 10, 26)
    assert cli.desat == [date(2026, 10, 1), date(2026, 11, 1)]
    r = _como(cli, "master@teste.local").post("/comercial/regras/janelas", data={
        "acao": "gravar", "lancamento": "PI-NOV-26", "inicio": "2026-11-03T00:00", "fim": "2026-11-02T00:00"})
    assert r.status_code == 400
    r = _como(cli, "master@teste.local").post("/comercial/regras/janelas", data={
        "acao": "gravar", "lancamento": "XX-NOV-26", "inicio": "2026-11-01", "fim": "2026-11-02"})
    assert r.status_code == 400
    _como(cli, "master@teste.local").post("/comercial/regras/janelas", data={"acao": "remover", "lancamento": "PI-NOV-26"})
    assert "PI-NOV-26" not in cli.banco.janelas and cli.desat[-1] is None


def test_meta_e_bonus_nao_invalidam(cli):
    r = _como(cli, "master@teste.local").post("/comercial/regras/metas",
                                               data={"vendedor_codigo": "AT4", "mes": "2026-11", "valor": "50.000"})
    assert r.headers["location"] == "/comercial/regras?mes_meta=2026-11&ok=meta_gravada#metas"
    assert cli.banco.metas[("AT4", date(2026, 11, 1))]["valor"] == D("50000.00")
    r = _como(cli, "coord@teste.local").post("/comercial/bonus", data={"vendedor_codigo": "AT9", "mes": "2026-10",
                                                                        "valor": "1.200,50", "justificativa": "meta batida"})
    assert r.headers["location"] == "/comercial/comissoes?mes=2026-10&ok=bonus_gravado"
    assert cli.banco.bonus[("AT9", date(2026, 10, 1))]["valor"] == D("1200.50")
    assert cli.desat == []
    r = _como(cli, "coord@teste.local").post("/comercial/bonus", data={"vendedor_codigo": "AT9", "mes": "2026-12",
                                                                        "valor": "1"})
    assert r.status_code == 400  # bônus só até o mês corrente


def test_comissoes_mostra_bonus_editavel_e_total(cli):
    cli.banco.bonus[("AT9", date(2026, 10, 1))] = {"valor": D("400"), "justificativa": "campanha"}
    cli.banco.bonus[("AT4", date(2026, 10, 1))] = {"valor": D("150"), "justificativa": None}
    html = _como(cli, "master@teste.local").get("/comercial/comissoes?mes=2026-10&ok=bonus_gravado").text
    assert 'action="/comercial/bonus"' in html and 'value="400,00"' in html
    assert "R$ 870,00" in html  # 320 elegível + 550 bônus
    assert rt.MENSAGENS_OK["bonus_gravado"] in html


def test_comissoes_vendedor_ve_so_o_proprio_bonus(cli):
    cli.banco.bonus[("AT9", date(2026, 10, 1))] = {"valor": D("400"), "justificativa": "segredo da jhe"}
    cli.banco.bonus[("AT4", date(2026, 10, 1))] = {"valor": D("150"), "justificativa": None}
    html = _como(cli, "edileia@teste.local").get("/comercial/comissoes?mes=2026-10").text
    assert "R$ 150,00" in html and "R$ 230,00" in html  # 80 + 150
    for proibido in ("R$ 400,00", "segredo da jhe", "Jheniffer", 'action="/comercial/bonus"'):
        assert proibido not in html, proibido


def test_ranking_meta_vendedor_e_gestor(cli):
    cli.banco.metas[("AT4", date(2026, 10, 1))] = {"valor": D("4000")}
    cli.banco.metas[("AT9", date(2026, 10, 1))] = {"valor": D("7777")}
    html = _como(cli, "edileia@teste.local").get("/comercial/ranking?mes=2026-10").text
    assert "R$ 4.000,00" in html and "50%" in html
    assert "R$ 7.777,00" not in html
    html = _como(cli, "master@teste.local").get("/comercial/ranking?mes=2026-10&ordem=meta").text
    assert "R$ 7.777,00" in html and "% da meta" in html


# ---------------------------------------------------------------- fix round 1
_XSS = "x');alert(document.domain);('@a.bc"


@pytest.mark.parametrize("ruim", [_XSS, 'a"b@x.com', "a<b@x.com", "a(b)@x.com", "a b@x.com", "a\b@x.com",
                                  "a@x.c'om", "a@x"])
def test_email_conservador_recusa_payload(ruim):
    with pytest.raises(rt.EntradaInvalida):
        rt.email(ruim)


def test_rota_recusa_email_com_payload(cli):
    r = _como(cli, "master@teste.local").post("/comercial/regras/acessos",
                                               data={"acao": "gravar", "email": _XSS, "nivel": "master"})
    assert r.status_code == 400 and cli.banco.escritas() == []


def test_pagina_nao_interpola_dado_em_js(cli):
    import re
    cli.banco.acessos[_XSS] = ("master", None)  # linha antiga/forjada direto no banco
    html = _como(cli, "master@teste.local").get("/comercial/regras").text
    for attr in re.findall(r'\son[a-z]+="([^"]*)"', html):
        assert "alert" not in attr and "document.domain" not in attr, attr
    assert "x&#39;);alert(document.domain);(&#39;@a.bc" in html  # só como texto escapado
    assert "x');alert" not in html
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
    assert all("alert(document" not in s for s in scripts)
    assert 'data-confirma="Remover o acesso de' in html


def test_primeira_janela_manual_invalida_meses_da_automatica(cli):
    # PBB-OUT-26: aulas 05/10 -> automática 05/10..13/10; manual em novembro tem de invalidar outubro
    r = _como(cli, "master@teste.local").post("/comercial/regras/janelas", data={
        "acao": "gravar", "lancamento": "PBB-OUT-26", "inicio": "2026-11-02", "fim": "2026-11-05"})
    assert r.status_code == 303
    assert cli.desat == [date(2026, 10, 1), date(2026, 11, 1)]


def test_janela_automatica(banco):
    assert com.janela_automatica("PBB-OUT-26") == (datetime(2026, 10, 5), datetime(2026, 10, 12, 23, 59, 59))
    assert com.janela_automatica("PI-NOV-26") is None


def test_linhas_janelas_mostra_a_em_vigor():
    b = FakeBanco()
    manual = {"PBB-OUT-26": {"inicio": datetime(2026, 10, 1), "fim": datetime(2026, 10, 3), "criado_por": "g"}}
    por = {j["lancamento"]: j for j in rt.linhas_janelas(b.lancamentos, manual)}
    assert por["PBB-OUT-26"]["vigor"] == (datetime(2026, 10, 1), datetime(2026, 10, 3))
    assert por["PES-NOV-26"]["vigor"] == por["PES-NOV-26"]["auto"]
    assert por["PI-NOV-26"]["vigor"] is None


def test_encerrar_padrao_e_o_mes_seguinte(cli):
    r = _como(cli, "master@teste.local").post("/comercial/regras/percentuais", data={"acao": "encerrar", "id": "1"})
    assert r.status_code == 303
    assert cli.banco.regras[0]["vigente_ate"] == date(2026, 11, 30)  # novembro continua com regra
    assert cli.desat == []  # dezembro ainda não existe
    _como(cli, "master@teste.local").post("/comercial/regras/participacoes", data={"acao": "encerrar", "id": "1"})
    assert cli.banco.parts[0]["vigente_ate"] == date(2026, 11, 30)


def test_form_encerrar_vem_com_mes_seguinte_e_confirmacao(cli):
    html = _como(cli, "master@teste.local").get("/comercial/regras").text
    bloco = html.split('name="acao" value="encerrar"')[1].split("</form>")[0]
    assert 'value="2026-12-01"' in bloco
    antes = html.split('name="acao" value="encerrar"')[0].rsplit("<form", 1)[1]
    assert "data-confirma=" in antes and "inconsistências" in antes


def test_reais_arredonda_meio_para_cima():
    assert rt.reais("10,005", "V") == D("10.01") and rt.reais("10,015", "V") == D("10.02")


def test_meta_e_bonus_sem_mudanca(banco):
    com.gravar_meta("AT4", date(2026, 11, 1), D("100.00"), "g@x")
    com.gravar_bonus("AT4", date(2026, 11, 1), D("50.00"), "x", "g@x")
    n = len(banco.historico)
    for fn in (lambda: com.gravar_meta("AT4", date(2026, 11, 1), D("100"), "g@x"),
               lambda: com.gravar_bonus("AT4", date(2026, 11, 1), D("50"), "x", "g@x")):
        with pytest.raises(com.EscritaRecusada) as e:
            fn()
        assert e.value.codigo == "sem_mudanca"
    assert len(banco.historico) == n
    com.gravar_bonus("AT4", date(2026, 11, 1), D("50"), "outro motivo", "g@x")  # justificativa mudou: grava
    assert len(banco.historico) == n + 1


def test_bonus_volta_com_o_filtro_de_vendedor(cli):
    r = _como(cli, "master@teste.local").post("/comercial/bonus", data={
        "vendedor_codigo": "AT9", "mes": "2026-10", "valor": "10", "vendedor": "at9"})
    assert r.headers["location"] == "/comercial/comissoes?mes=2026-10&vendedor=AT9&ok=bonus_gravado"
    r = _como(cli, "master@teste.local").post("/comercial/bonus", data={
        "vendedor_codigo": "AT9", "mes": "2026-10", "valor": "11", "vendedor": "x&ok=1"})
    assert r.headers["location"] == "/comercial/comissoes?mes=2026-10&ok=bonus_gravado"
