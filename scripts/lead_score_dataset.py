"""
scripts/lead_score_dataset.py — monta a base de treino do lead score (pesquisa × compra), um arquivo por lançamento.

Cada linha = um lead do lançamento (lead_utm_lancamento); colunas = resposta (normalizada) das perguntas-padrão da
pesquisa, `respondeu` (respondeu a pesquisa) e `comprou` (e-mail com venda Hotmart/TMB no lançamento).
Somente leitura. Dados pessoais: grava só e-mail + respostas, em --saida (fora do git).

    python scripts/lead_score_dataset.py --saida <pasta> [--launch PES-SET-26 ...]
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import frontend.db_readers.typeform as T  # noqa: E402
from frontend.db import _get_engine  # noqa: E402
from frontend.db_readers.sales import read_vendas  # noqa: E402
from sqlalchemy import text  # noqa: E402

# Perguntas que se repetem em todos os lançamentos (texto normalizado, sem acento). O nome do expert e do concurso
# mudam entre produtos, então o agulheiro evita esses termos.
PERGUNTAS = {
    "idade": r"\bidade\b",
    "genero": r"\bgenero\b",
    "estado": r"qual estado|de qual estado",
    "filhos": r"quantos filhos",
    "mora": r"com quem voce mora",
    "escolaridade": r"escolaridade",
    "situacao": r"situacao profissional",
    "viu_expert": r"assistiu a algum video|assistiu algum video|ja assistiu",
    "motivo": r"porque voce decidiu|por que voce decidiu",
    "nivel": r"voce se considera",
    "prestou": r"ja prestou algum concurso",
    "compromisso": r"se compromete",
}


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


_VOCAB: dict[str, dict[str, int]] | None = None
_REF = ("PES-SET-26", "PBB-AGO-26", "PI-NOV-26")     # lançamentos com o título da pergunta preservado


def _colunas_padrao(tf: pd.DataFrame) -> dict[str, str]:
    cols = {}
    for chave, padrao in PERGUNTAS.items():
        col = next((c for c in tf.columns if c != "email_norm" and re.search(padrao, _norm(c))), None)
        if col:
            cols[chave] = col
    return cols


def vocabulario() -> dict[str, dict[str, int]]:
    """{pergunta-padrão: {resposta normalizada: nº de vezes}} dos lançamentos com título de pergunta."""
    global _VOCAB
    if _VOCAB is None:
        voc: dict[str, dict[str, int]] = {q: {} for q in PERGUNTAS}
        for code in _REF:
            tf = respostas(code, mapear=False)
            for chave, col in _colunas_padrao(tf).items():
                for v, n in tf[col].dropna().map(_norm).value_counts().items():
                    voc[chave][v] = voc[chave].get(v, 0) + int(n)
        _VOCAB = voc
    return _VOCAB


def _mapear_campos(raw: pd.DataFrame) -> dict[str, str]:
    """Campo (id) → pergunta-padrão, pelo conjunto de respostas. Só aceita quando um campo casa com UMA pergunta
    (≥85% das respostas no vocabulário dela e nenhuma outra com ≥50%) — campos Sim/Não ficam de fora."""
    voc = vocabulario()
    achado: dict[str, str] = {}
    for campo in [c for c in raw.columns if c != "email_norm"]:
        vals = raw[campo].dropna().map(_norm)
        vals = vals[vals != ""]
        if len(vals) < 200:
            continue
        cob = {q: float(vals.isin(set(v)).mean()) for q, v in voc.items() if v}
        melhor = sorted(cob.items(), key=lambda kv: -kv[1])
        if melhor[0][1] >= 0.85 and (len(melhor) < 2 or melhor[1][1] < 0.5):
            achado[campo] = melhor[0][0]
    # uma pergunta só pode ter um campo: em empate fica o de mais respostas
    por_q: dict[str, str] = {}
    for campo, q in achado.items():
        if q not in por_q or raw[campo].notna().sum() > raw[por_q[q]].notna().sum():
            por_q[q] = campo
    return {campo: q for q, campo in por_q.items()}


def respostas(code: str, mapear: bool = True) -> pd.DataFrame:
    proj_id, _ = T._resolve_typeform_ids(code)
    proj_id = proj_id or code
    where = ("upper(coalesce(form_id, '')) = :fid AND lower(email) IN "
             "(SELECT email FROM lead_utm_lancamento WHERE lancamento_codigo = :code AND email <> '')")
    if mapear and not T._tem_titulo_legivel(proj_id.upper()):
        # Typeform antigo: as respostas estão no banco, mas as chaves são ids de campo. Lê o JSON inteiro e traduz.
        with _get_engine().connect() as c:
            c.execute(text("SET LOCAL statement_timeout = 180000"))
            linhas = c.execute(text(f"SELECT email_norm, valores FROM {T._TF_VALORES} WHERE {where}"),
                               {"fid": proj_id.upper(), "code": code}).fetchall()
        a = pd.DataFrame([{"email_norm": e, **(v or {})} for e, v in linhas])
        if not a.empty:
            mapa = _mapear_campos(a)
            a = a[["email_norm", *mapa]].rename(columns={c: f"__{q}" for c, q in mapa.items()})
            a = a.rename(columns={f"__{q}": q for q in mapa.values()})
            a.attrs["ja_padrao"] = True
    else:
        a = pd.DataFrame(T._registros_materializados(where, {"fid": proj_id.upper(), "code": code}, proj_id.upper()))
    b = T._novo_sistema_respostas_cached(code)
    tf = pd.concat([a, b], ignore_index=True, sort=False)
    if tf.empty:
        return tf
    return tf.drop_duplicates("email_norm", keep="last")


def montar(code: str) -> pd.DataFrame | None:
    with _get_engine().connect() as c:
        c.execute(text("SET LOCAL statement_timeout = 180000"))
        leads = [r[0] for r in c.execute(text(
            "SELECT DISTINCT email FROM lead_utm_lancamento WHERE lancamento_codigo = :c AND email <> ''"), {"c": code})]
    if not leads:
        return None
    v = read_vendas(code)
    compradores = (v.emails_hotmart | v.emails_tmb) if v else set()
    tf = respostas(code)
    df = pd.DataFrame({"email": leads})
    df["comprou"] = df["email"].isin(compradores)
    df["respondeu"] = False
    for chave in PERGUNTAS:
        df[chave] = None
    if not tf.empty:
        cols = {}
        for chave, padrao in PERGUNTAS.items():
            if chave in tf.columns:                       # Typeform antigo, já traduzido por _mapear_campos
                cols[chave] = chave
                continue
            col = next((c for c in tf.columns if c != "email_norm" and re.search(padrao, _norm(c))), None)
            if col:
                cols[chave] = col
        sub = tf[["email_norm", *cols.values()]].rename(columns={v_: k for k, v_ in cols.items()})
        sub = sub.rename(columns={"email_norm": "email"})
        df = df.drop(columns=list(cols)).merge(sub, on="email", how="left") if cols else df
        df["respondeu"] = df["email"].isin(set(tf["email_norm"].dropna()))
        for chave in PERGUNTAS:
            if chave not in df.columns:
                df[chave] = None
    df["launch"] = code
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", required=True)
    ap.add_argument("--launch", nargs="*")
    args = ap.parse_args()
    out = Path(args.saida)
    out.mkdir(parents=True, exist_ok=True)
    with _get_engine().connect() as c:
        codigos = [r[0] for r in c.execute(text(
            "SELECT codigo FROM dim_lancamentos WHERE codigo ~ '^(PES|PI|PBB)-' ORDER BY data_inicio"))]
    for code in (args.launch or codigos):
        t = time.time()
        try:
            df = montar(code)
        except Exception as e:  # noqa: BLE001
            print(f"{code}: ERRO {type(e).__name__}: {str(e)[:120]}", flush=True)
            continue
        if df is None:
            print(f"{code}: sem leads", flush=True)
            continue
        df.to_pickle(out / f"{code}.pkl")
        print(f"{code}: leads={len(df)} respondeu={int(df['respondeu'].sum())} comprou={int(df['comprou'].sum())} "
              f"({time.time() - t:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
