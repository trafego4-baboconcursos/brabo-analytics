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
# Pergunta de múltipla escolha ("3 opções que mais preocupam você"): cada opção é uma variável 0/1. O trecho é o texto da
# opção sem acento e em minúsculas; a mesma lista vai no JSON do modelo e é usada por `frontend/services/lead_score.py`.
OPCOES_PREOCUP = ["nao sei estudar do jeito certo", "nao sei montar um cronograma", "estou ha muito tempo sem estudar",
                  "nao tenho dinheiro para investir", "medo de estudar muito", "pouco tempo disponivel",
                  "medo de esquecer tudo", "procrastinacao", "estou velho para comecar",
                  "medo de nao sair o concurso", "medo de nao dar tempo"]


def _norm_txt(v) -> str:
    import unicodedata
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


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
    df["preocup"] = df["preocup"].map(_norm_txt) if "preocup" in df else ""
    df["respondeu"] = df["respondeu"].astype(int)
    df["y"] = df["comprou"].astype(int)
    df["produto"] = df["launch"].str.split("-").str[0]
    return df


class Modelo:
    def __init__(self, c: float = 0.5, multi: bool = True):
        self.c = c
        self.multi = multi          # usa as opções de preocupação (múltipla escolha)

    def _x(self, df: pd.DataFrame) -> np.ndarray:
        cols = []
        for q in PERGUNTAS:
            ok = df[q].isin(self.vocab[q])
            s = df[q].where(ok, "")
            cols.append(pd.get_dummies(s).reindex(columns=self.vocab[q], fill_value=0).astype(np.float32))
        if self.multi:
            t = df["preocup"].fillna("").map(_norm_txt)
            cols.append(pd.DataFrame({o: t.map(lambda s, o=o: 1.0 if o in s else 0.0) for o in OPCOES_PREOCUP}, index=df.index).astype(np.float32))
        x = pd.concat(cols, axis=1)
        x.insert(0, "respondeu", df["respondeu"].astype(np.float32).values)
        return x.values

    def fit(self, df: pd.DataFrame) -> "Modelo":
        self.vocab = {q: [v for v, n in df[q].value_counts().items() if v and n >= MIN_RESPOSTA] for q in PERGUNTAS}
        self.nomes = (["respondeu"] + [f"{q}={v}" for q in PERGUNTAS for v in self.vocab[q]]
                      + ([f"preocup={o}" for o in OPCOES_PREOCUP] if self.multi else []))
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
    ap.add_argument("--exportar", help="grava o modelo treinado (JSON) para o painel calcular o score sem retreinar")
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
        sem = Modelo(a.c, multi=False).fit(tr).prever(te)  # mesmo modelo sem as opções de preocupação (comparação)
        a3 = roc_auc_score(te["y"].values[mr], sem[mr])
        aucs.append((a0, a1, a2, a3))
        q = lift_por_decil(te["y"].values, p)
        print(f"{code:<12}{len(te):>8}{100 * te['respondeu'].mean():>7.1f}{100 * te['y'].mean():>7.2f} | {a0:>17.3f}{a1:>12.3f}{a2:>10.3f} | "
              f"{100 * q[0][0]:.2f}% / {100 * q[-1][0]:.2f}% ({q[0][1]:.1f}x) | resp. sem preocupações {a3:.3f}")
    print(f"{'MÉDIA':<12}{'':>8}{'':>7}{'':>7} | {np.mean([x[0] for x in aucs]):>17.3f}{np.mean([x[1] for x in aucs]):>12.3f}{np.mean([x[2] for x in aucs]):>10.3f}"
          f" | resp. sem preocupações {np.mean([x[3] for x in aucs]):.3f}")

    m = Modelo(a.c).fit(df)
    w = pd.Series(m.lr.coef_[0], index=m.nomes).sort_values()
    print("\nPesos (log-odds; positivo = mais chance de comprar)")
    print(w.tail(12).round(2).to_string()); print("..."); print(w.head(8).round(2).to_string())

    if a.exportar:
        import json
        resp = df[df["respondeu"] == 1]
        p_resp = m.prever(resp)
        modelo = {
            "perguntas": PERGUNTAS,
            "vocab": m.vocab,
            "intercepto": float(m.lr.intercept_[0]),
            "coef": [float(x) for x in m.lr.coef_[0]],          # 1º = respondeu; depois uma coluna por (pergunta, resposta); no fim, uma por opção de preocupação
            "multi": {"preocup": OPCOES_PREOCUP},               # opções 0/1 (trecho sem acento contido no texto da resposta)
            "limiar_a": float(np.median(p_resp)),                # A = respondeu com probabilidade acima da mediana dos respondentes
            "lancamentos": sorted(df["launch"].unique().tolist()),
            "auc_medio_validacao": float(np.mean([x[1] for x in aucs])),
            "auc_medio_entre_respondentes": float(np.mean([x[2] for x in aucs])),
        }
        Path(a.exportar).write_text(json.dumps(modelo, ensure_ascii=False), encoding="utf-8")
        print("modelo exportado:", a.exportar)

    if a.score and a.saida:
        alvo = pd.read_pickle(Path(a.entrada) / f"{a.score}.pkl")
        alvo["comprou"] = alvo["comprou"].astype(bool)
        for q in PERGUNTAS:
            alvo[q] = alvo[q].map(_limpa)
        alvo["preocup"] = alvo["preocup"].map(_norm_txt) if "preocup" in alvo else ""
        alvo["respondeu"] = alvo["respondeu"].astype(int)
        p = m.prever(alvo)
        pct = pd.Series(p).rank(pct=True).values * 100
        alvo["score"] = np.round(pct).astype(int)
        alvo["faixa"] = pd.cut(alvo["score"], [-1, 39, 79, 100], labels=["C", "B", "A"])
        alvo[["email", "score", "faixa", "respondeu"]].to_csv(a.saida, index=False)
        print("\nscore gravado:", a.saida, alvo["faixa"].value_counts().to_dict())


if __name__ == "__main__":
    main()
