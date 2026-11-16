"""
scripts/lead_score_treino.py — treina e valida o lead score (pesquisa → chance de compra).

Lê os .pkl de `lead_score_dataset.py`. Modelo: regressão logística com uma coluna por (pergunta, resposta) + `respondeu`.
Validação "deixa um lançamento de fora": treina em todos os outros e mede no que ficou — é isso que diz se o score
funciona em lançamento novo. Compara com a base mais simples (só `respondeu`).

    python scripts/lead_score_treino.py --entrada <pasta> [--score PES-NOV-26 --saida <csv>]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

PERGUNTAS = ["idade", "genero", "estado", "filhos", "mora", "escolaridade", "situacao", "nivel"]   # presentes em TODOS os lançamentos
MIN_RESPOSTA = 300     # respostas raras (menos que isso no treino) viram "outra"


def _limpa(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip().lower()[:60]


def carregar(pasta: Path, codigos: list[str] | None = None) -> pd.DataFrame:
    dfs = []
    for p in sorted(pasta.glob("*.pkl")):
        if codigos and p.stem not in codigos:
            continue
        d = pd.read_pickle(p)
        # só lançamento com pesquisa e venda de verdade entra no treino
        if d["respondeu"].sum() < 500 or d["comprou"].sum() < 100:
            continue
        dfs.append(d)
    df = pd.concat(dfs, ignore_index=True)
    for q in PERGUNTAS:
        df[q] = df[q].map(_limpa)
    df["respondeu"] = df["respondeu"].astype(int)
    df["y"] = df["comprou"].astype(int)
    df["produto"] = df["launch"].str.split("-").str[0]
    return df


class Modelo:
    def __init__(self, c: float = 0.5):
        self.c = c

    def _x(self, df: pd.DataFrame) -> np.ndarray:
        cols = []
        for q in PERGUNTAS:
            ok = df[q].isin(self.vocab[q])
            s = df[q].where(ok, "")
            cols.append(pd.get_dummies(s).reindex(columns=self.vocab[q], fill_value=0).astype(float))
        x = pd.concat(cols, axis=1)
        x.insert(0, "respondeu", df["respondeu"].astype(float).values)
        return x.values

    def fit(self, df: pd.DataFrame) -> "Modelo":
        self.vocab = {q: [v for v, n in df[q].value_counts().items() if v and n >= MIN_RESPOSTA] for q in PERGUNTAS}
        self.nomes = ["respondeu"] + [f"{q}={v}" for q in PERGUNTAS for v in self.vocab[q]]
        self.lr = LogisticRegression(C=self.c, max_iter=400)
        self.lr.fit(self._x(df), df["y"].values)
        return self

    def prever(self, df: pd.DataFrame) -> np.ndarray:
        return self.lr.predict_proba(self._x(df))[:, 1]


def lift_por_decil(y: np.ndarray, p: np.ndarray, n: int = 5) -> list[tuple[float, float]]:
    """Taxa de compra por quintil de score (do mais alto ao mais baixo) e o lift sobre a taxa geral."""
    d = pd.DataFrame({"y": y, "p": p}).sort_values("p", ascending=False).reset_index(drop=True)
    d["q"] = (np.arange(len(d)) * n // len(d))
    base = d["y"].mean()
    g = d.groupby("q")["y"].mean()
    return [(float(g[i]), float(g[i] / base) if base else 0.0) for i in range(n)]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", required=True)
    ap.add_argument("--score")
    ap.add_argument("--saida")
    ap.add_argument("--c", type=float, default=0.5)
    ap.add_argument("--excluir", default="PES-NOV-26,PI-NOV-26", help="carrinho aberto: fora do treino e da validação")
    a = ap.parse_args()
    df = carregar(Path(a.entrada))
    df = df[~df["launch"].isin(a.excluir.split(","))]
    print("lançamentos no treino:", ", ".join(sorted(df["launch"].unique())))
    print(f"{'lançamento':<12}{'leads':>8}{'resp%':>7}{'comp%':>7} | {'AUC só-respondeu':>17}{'AUC modelo':>12}{'AUC resp.':>10} | top20% / base20% (lift)")
    aucs = []
    for code in sorted(df["launch"].unique()):
        te = df[df["launch"] == code]
        tr = df[df["launch"] != code]
        m = Modelo(a.c).fit(tr)
        p = m.prever(te)
        base = te["respondeu"].values.astype(float)
        a0 = roc_auc_score(te["y"], base)
        a1 = roc_auc_score(te["y"], p)
        mr = te["respondeu"].values == 1
        a2 = roc_auc_score(te["y"].values[mr], p[mr])      # só entre quem respondeu: o valor das respostas em si
        aucs.append((a0, a1, a2))
        q = lift_por_decil(te["y"].values, p)
        print(f"{code:<12}{len(te):>8}{100 * te['respondeu'].mean():>7.1f}{100 * te['y'].mean():>7.2f} | {a0:>17.3f}{a1:>12.3f}{a2:>10.3f} | "
              f"{100 * q[0][0]:.2f}% / {100 * q[-1][0]:.2f}% ({q[0][1]:.1f}x)")
    print(f"{'MÉDIA':<12}{'':>8}{'':>7}{'':>7} | {np.mean([x[0] for x in aucs]):>17.3f}{np.mean([x[1] for x in aucs]):>12.3f}{np.mean([x[2] for x in aucs]):>10.3f}")

    m = Modelo(a.c).fit(df)
    w = pd.Series(m.lr.coef_[0], index=m.nomes).sort_values()
    print("\nPesos (log-odds; positivo = mais chance de comprar)")
    print(w.tail(12).round(2).to_string()); print("..."); print(w.head(8).round(2).to_string())

    if a.score and a.saida:
        alvo = pd.read_pickle(Path(a.entrada) / f"{a.score}.pkl")
        alvo["comprou"] = alvo["comprou"].astype(bool)
        for q in PERGUNTAS:
            alvo[q] = alvo[q].map(_limpa)
        alvo["respondeu"] = alvo["respondeu"].astype(int)
        p = m.prever(alvo)
        pct = pd.Series(p).rank(pct=True).values * 100
        alvo["score"] = np.round(pct).astype(int)
        alvo["faixa"] = pd.cut(alvo["score"], [-1, 39, 79, 100], labels=["C", "B", "A"])
        alvo[["email", "score", "faixa", "respondeu"]].to_csv(a.saida, index=False)
        print("\nscore gravado:", a.saida, alvo["faixa"].value_counts().to_dict())


if __name__ == "__main__":
    main()
