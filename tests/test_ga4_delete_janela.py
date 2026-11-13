"""_delete_janela do etl_ga4: propriedade que falhou não pode ter o histórico apagado."""
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
import etl_ga4  # noqa: E402


def _engine():
    e = create_engine("sqlite://")
    with e.begin() as c:
        c.execute(text("CREATE TABLE t (date TEXT, property_id TEXT)"))
        for d in ("2026-11-11", "2026-11-12", "2026-11-13"):
            for p in ("A", "B"):
                c.execute(text("INSERT INTO t VALUES (:d, :p)"), {"d": d, "p": p})
    return e


def _restantes(e):
    with e.connect() as c:
        return sorted(tuple(r) for r in c.execute(text("SELECT date, property_id FROM t")))


def test_delete_so_das_propriedades_que_responderam():
    e = _engine()
    with e.begin() as c:
        etl_ga4._delete_janela(c, "t", "2026-11-12", "2026-11-13", ["A"])
    r = _restantes(e)
    assert ("2026-11-12", "A") not in r and ("2026-11-13", "A") not in r
    assert ("2026-11-12", "B") in r and ("2026-11-13", "B") in r      # B falhou: mantém
    assert ("2026-11-11", "A") in r                                    # fora da janela: mantém


def test_sem_nenhuma_propriedade_ok_nao_apaga_nada():
    e = _engine()
    with e.begin() as c:
        etl_ga4._delete_janela(c, "t", "2026-11-11", "2026-11-13", [])
    assert len(_restantes(e)) == 6


def test_sem_lista_mantem_o_comportamento_antigo():
    e = _engine()
    with e.begin() as c:
        etl_ga4._delete_janela(c, "t", "2026-11-12", "2026-11-13", None)
    assert [d for d, _ in _restantes(e)] == ["2026-11-11", "2026-11-11"]
