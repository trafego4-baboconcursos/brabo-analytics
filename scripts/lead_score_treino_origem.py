"""
scripts/lead_score_treino_origem.py — treina o score POR LEAD com origem (canal, temperatura, etapa) e grava
`config/lead_score_modelo_origem.json`, usado por `frontend/services/lead_score.py::calcular_leads` (CSV de
/leads/score.csv). É um modelo à parte do `lead_score_modelo.json` (bloco do debriefing, só pesquisa).

Por que à parte: o canal entra no score, então ele serve para priorizar o lead, não para julgar anúncio.
Pontua também quem NÃO respondeu a pesquisa (`respondeu`=0 + origem).

Cuidados que vieram da investigação de 17/11/26 (ver ARQUITETURA, «Histórico de UTM por lançamento»):
  - as linhas de `lead_utm_lancamento` criadas por carga (`etl_ac`/`export_ac`) concentram os compradores; por isso o
    TIPO DE LINHA entra no treino como variável de controle (1 coluna, `carga`) e a nota sai com ela zerada;
  - treina só nos lançamentos de 2026 (a temperatura quente/frio só existe nas campanhas de mai/26 em diante);
  - para caber na memória só uma fração dos não compradores entra no treino; o intercepto é corrigido (ln da fração).

    python scripts/lead_score_dataset.py --saida <pasta>                      # base de treino (1 vez por lançamento novo)
    python scripts/lead_score_treino_origem.py --entrada <pasta> --exportar config/lead_score_modelo_origem.json
    python scripts/lead_score_treino_origem.py --entrada <pasta> --validar    # deixa um lançamento de fora por vez
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import scipy.sparse as sp  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sqlalchemy import text  # noqa: E402

import lead_score_treino as T  # noqa: E402
from frontend.db import _get_engine  # noqa: E402
from frontend.services.lead_score import derivar_origem  # noqa: E402

FRACAO_NAO_COMPRADORES = 0.25      # fração dos não compradores que entra no treino (memória); intercepto corrigido
MIN_CATEGORIA = 300                # categoria de origem com menos leads que isso não vira variável
CAMPOS_ORIGEM = ("canal", "temp", "etapa")
C = 0.5


def _carregar(pasta: Path, excluir: set[str]) -> dict[str, pd.DataFrame]:
    """{lançamento: base com origem} dos lançamentos de 2026 fechados com pesquisa e vendas suficientes."""
    sql = text("SELECT DISTINCT ON (email) email, origem, utm_source, utm_campaign FROM lead_utm_lancamento "
               "WHERE lancamento_codigo = :c AND email <> '' ORDER BY email, primeiro_visto_em")
    out: dict[str, pd.DataFrame] = {}
    for p in sorted(pasta.glob("*-26.pkl")):
        code = p.stem
        if code in excluir:
            continue
        d = pd.read_pickle(p)
        if d["respondeu"].sum() < 500 or d["comprou"].sum() < 100:
            continue
        with _get_engine().connect() as c:
            c.execute(text("SET LOCAL statement_timeout = 300000"))
            rows = c.execute(sql, {"c": code}).fetchall()
        u = pd.DataFrame(rows, columns=["email", "origem_registro", "utm_source", "utm_campaign"])
        u = pd.concat([u[["email", "origem_registro"]], derivar_origem(u["utm_source"], u["utm_campaign"])], axis=1)
        d = d.merge(u, on="email", how="left")
        for q in T.PERGUNTAS:
            d[q] = d[q].map(T._limpa)
        d["preocup"] = d["preocup"].map(T._norm_txt) if "preocup" in d else ""
        d["respondeu"] = d["respondeu"].astype(int)
        d["y"] = d["comprou"].astype(int)
        d["launch"] = code
        d["carga"] = (~d["origem_registro"].isin(["seed_leads", "seed_fallback"])).astype(int)
        for c_ in CAMPOS_ORIGEM:
            d[c_] = d[c_].fillna("vazio").astype(str)
        out[code] = d[["email", "y", "respondeu", "launch", "carga", "preocup", *T.PERGUNTAS, *CAMPOS_ORIGEM]]
        print(f"{code}: leads={len(d)} compradores={int(d['y'].sum())}", flush=True)
    return out


def _amostra(d: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([d[d["y"] == 1], d[d["y"] == 0].sample(frac=FRACAO_NAO_COMPRADORES, random_state=1)],
                     ignore_index=True)


class ModeloOrigem:
    def __init__(self, com_origem: bool = True):
        self.com_origem = com_origem

    def _x(self, df: pd.DataFrame) -> sp.csr_matrix:
        parts = [sp.csr_matrix(self.base._x(df)), sp.csr_matrix(df[["carga"]].to_numpy(dtype=np.float32))]
        if self.com_origem:
            for campo, valor in self.cols:
                parts.append(sp.csr_matrix((df[campo].to_numpy() == valor).astype(np.float32).reshape(-1, 1)))
        return sp.hstack(parts).tocsr()

    def fit(self, df: pd.DataFrame) -> "ModeloOrigem":
        self.base = T.Modelo(C)                     # só para a codificação de respondeu/respostas/preocupações
        self.base.vocab = {q: [v for v, n in df[q].value_counts().items() if v and n >= T.MIN_RESPOSTA]
                           for q in T.PERGUNTAS}
        self.cols = [(c, v) for c in CAMPOS_ORIGEM for v, n in df[c].value_counts().items() if n >= MIN_CATEGORIA]
        self.lr = LogisticRegression(C=C, max_iter=300).fit(self._x(df), df["y"].values)
        return self

    def prever(self, df: pd.DataFrame) -> np.ndarray:
        return self.lr.predict_proba(self._x(df))[:, 1]


def _auc(y: np.ndarray, p: np.ndarray, mascara: np.ndarray) -> float:
    y, p = y[mascara], p[mascara]
    return float(roc_auc_score(y, p)) if y.sum() >= 40 and (1 - y).sum() >= 40 else float("nan")


def validar(bases: dict[str, pd.DataFrame]) -> None:
    """Deixa um lançamento de fora por vez: AUC DENTRO de cada tipo de linha, sem e com origem."""
    print(f"\n{'teste':<12}{'dentro de carga (sem → com origem)':>38}{'dentro de cadastro':>26}{'não-resp. em carga':>22}")
    res = []
    for code, te in bases.items():
        tr = pd.concat([_amostra(d) for c, d in bases.items() if c != code], ignore_index=True)
        y, ca, nr = te["y"].to_numpy(), te["carga"].to_numpy() == 1, te["respondeu"].to_numpy() == 0
        r = []
        for com in (False, True):
            p = ModeloOrigem(com).fit(tr).prever(te)
            r += [_auc(y, p, ca), _auc(y, p, ~ca), _auc(y, p, nr & ca)]
        res.append(r)
        print(f"{code:<12}{r[0]:>17.3f} →{r[3]:>6.3f}{r[1]:>14.3f} →{r[4]:>6.3f}{r[5]:>22.3f}", flush=True)
    m = np.nanmean(np.array(res), axis=0)
    print(f"{'MÉDIA':<12}{m[0]:>17.3f} →{m[3]:>6.3f}{m[1]:>14.3f} →{m[4]:>6.3f}{m[5]:>22.3f}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", required=True, help="pasta dos .pkl de lead_score_dataset.py")
    ap.add_argument("--exportar", help="grava o modelo (JSON) para o painel")
    ap.add_argument("--validar", action="store_true")
    ap.add_argument("--excluir", default="PES-NOV-26,PI-NOV-26", help="carrinho aberto: fora do treino")
    a = ap.parse_args()
    bases = _carregar(Path(a.entrada), set(a.excluir.split(",")))
    if a.validar:
        validar(bases)
    if a.exportar:
        tr = pd.concat([_amostra(d) for d in bases.values()], ignore_index=True)
        m = ModeloOrigem(True).fit(tr)
        coef = [float(x) for x in m.lr.coef_[0]]
        modelo = {
            "perguntas": T.PERGUNTAS,
            "vocab": m.base.vocab,
            "multi": {"preocup": T.OPCOES_PREOCUP},
            "colunas_controle": 1,                                       # «carga» (tipo de linha): vale 0 ao pontuar
            "origem": {"cols": [list(c) for c in m.cols]},
            "intercepto": float(m.lr.intercept_[0]) + float(np.log(FRACAO_NAO_COMPRADORES)),
            "coef": coef,        # respondeu, escolha única, preocupações, carga, origem (nessa ordem)
            "lancamentos": sorted(bases),
            "observacao": "ordena leads; a probabilidade absoluta não é calibrada (intercepto corrigido pela amostra)",
        }
        Path(a.exportar).write_text(json.dumps(modelo, ensure_ascii=False), encoding="utf-8")
        print("modelo exportado:", a.exportar, "| coeficientes:", len(coef))


if __name__ == "__main__":
    main()
