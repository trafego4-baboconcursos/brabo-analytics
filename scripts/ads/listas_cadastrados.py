"""Lista de cadastrados do lançamento (tabela `leads`) no Facebook (Meta) e no Google, para a exclusão da regra SEG-4.

    python -m scripts.ads.listas_cadastrados --criar PI-NOV-26      # cria as duas listas (a do Google fica vazia: VER-5)
    python -m scripts.ads.listas_cadastrados PES-NOV-26             # atualiza agora as listas de um lançamento
    python -m scripts.ads.listas_cadastrados --ativos               # o que o scheduler roda todo dia
    python -m scripts.ads.listas_cadastrados --status <request_id> [...]

O público de site `[SITE] Cadastrados [<LANC>]` só tem quem o pixel/tag registrou na página de obrigado: no PES-NOV-26
eram 5–11 mil de 37,7 mil leads (MUDANCAS_PES-NOV-26 itens 107–108). Esta lista vem do banco e cobre todos.
Nas duas plataformas a lista só cresce (Meta POST /users; Google Data Manager acrescenta): a `leads` tem uma linha por
contato e quem se cadastra no lançamento seguinte some da consulta deste — substituir tiraria essa pessoa da exclusão. Depois de `--criar`, copiar os IDs para `padroes.LISTAS_CADASTRADOS`.
Sai com 1 se qualquer plataforma falhar (o scheduler alerta).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from scripts.ads import padroes as P

RAIZ = Path(__file__).resolve().parents[2]
LOG = RAIZ / "outputs" / "customer_match_requests.jsonl"
NOME_META = "[Lista] Cadastrados [{lanc}]"
NOME_GOOGLE = "[LISTA] Cadastrados [{lanc}] - 540 dias"


# ---------------------------------------------------------------------------- funções puras (testadas)
def pessoas_unicas(linhas) -> list[dict]:
    """(email, telefone, nome, sobrenome) → uma pessoa por e-mail, sem e-mail vazio."""
    out: dict[str, dict] = {}
    for email, tel, nome, sobrenome in linhas:
        e = (email or "").strip().lower()
        if e and e not in out:
            out[e] = {"email": e, "phone": tel, "first_name": nome or "", "last_name": sobrenome or ""}
    return list(out.values())


def lancamentos_ativos(mapa: dict, hoje: dt.date) -> list[str]:
    return [lanc for lanc, cfg in mapa.items() if dt.date.fromisoformat(cfg["ate"]) >= hoje]


def google_pode_ingerir(cfg: dict, hoje: dt.date) -> bool:
    """VER-5: não ingerir no mesmo dia em que a lista foi criada."""
    criada = cfg.get("google_criada")
    return not criada or dt.date.fromisoformat(criada) < hoje


# ---------------------------------------------------------------------------- banco e plataformas
def pessoas_do_lancamento(lanc: str) -> list[dict]:
    from sqlalchemy import text
    from etl.db import get_engine
    with get_engine().connect() as c:
        c.execute(text("SET LOCAL statement_timeout = 180000"))
        linhas = c.execute(text("SELECT email, phone, nome, sobrenome FROM leads WHERE lancamento_codigo = :l"),
                           {"l": lanc}).fetchall()
    return pessoas_unicas(linhas)


def atualizar_meta(m, audience_id: str, pessoas: list[dict]) -> int:
    return m.adicionar_membros(audience_id, pessoas)


def atualizar_google(g, conta: str, lista_id: str, pessoas: list[dict], lanc: str) -> list[str]:
    ids = g.customer_match(conta, lista_id, pessoas)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        for rid in ids:
            f.write(json.dumps({"quando": dt.datetime.now().isoformat(timespec="seconds"), "lancamento": lanc,
                                "conta": conta, "lista": lista_id, "request_id": rid, "pessoas": len(pessoas)}) + "\n")
    return ids


def criar(lanc: str) -> dict:
    """Cria a lista no Meta (conta de públicos da CA2, compartilhada com as contas de campanha) e preenche; no Google cria
    vazia na conta de lançamentos. Reaproveita a que já existe com o mesmo nome."""
    from scripts.ads.google import Google
    from scripts.ads.meta import Meta
    m, dono = Meta(), P.META_CONTAS["ca2_publicos"]
    nome = NOME_META.format(lanc=lanc)
    ja = [a["id"] for a in m.listar(f"{dono}/customaudiences", fields="id,name", limit=500) if a["name"] == nome]
    aid = ja[0] if ja else m.post(
        f"{dono}/customaudiences", name=nome, subtype="CUSTOM", customer_file_source="USER_PROVIDED_ONLY",
        description=f"Todos os cadastrados do {lanc} (tabela leads). Exclusão SEG-4; atualizada todo dia.")["id"]
    print(f"Meta: {'já existia' if ja else 'criado'} {aid} {nome}")
    pessoas = pessoas_do_lancamento(lanc)
    print(f"Meta: {atualizar_meta(m, aid, pessoas)} pessoas enviadas")
    m.compartilhar_publico(aid, [P.META_CONTAS["ca2_anunciante"], P.META_CONTAS["ivan_pes"]])
    conta = P.GOOGLE_CONTAS["lancamentos"]
    nome_g = NOME_GOOGLE.format(lanc=lanc)
    g = Google()
    ja_g = [r["userList"]["id"] for r in g.buscar(conta, "SELECT user_list.id, user_list.name FROM user_list")
            if r["userList"]["name"] == nome_g]
    if ja_g:
        gid = ja_g[0]
    else:
        sys.path.insert(0, str(RAIZ / "scripts-python"))
        from upload_lista_google_ads import create_user_list, get_authenticated_clients
        gid = create_user_list(get_authenticated_clients()[0], conta, nome_g,
                               f"Todos os cadastrados do {lanc} (tabela leads). Exclusao SEG-4. Ingerir 1 dia apos criar (VER-5).")
    print(f"Google: {'já existia' if ja_g else 'criada vazia'} {gid} {nome_g}")
    cfg = {"meta": aid, "google": (conta, gid), "google_criada": dt.date.today().isoformat()}
    print(f"Copiar para padroes.LISTAS_CADASTRADOS (com 'ate' = fim da captação): {json.dumps({lanc: cfg})}")
    return cfg


def atualizar(lanc: str, cfg: dict, hoje: dt.date, *, forcar_google: bool = False) -> bool:
    from scripts.ads.google import Google
    from scripts.ads.meta import Meta
    pessoas = pessoas_do_lancamento(lanc)
    ok = True
    try:
        print(f"{lanc} Meta {cfg['meta']}: {atualizar_meta(Meta(), cfg['meta'], pessoas)} de {len(pessoas)} enviadas")
    except Exception as e:  # noqa: BLE001 — uma plataforma não derruba a outra; o exit code avisa
        ok = False
        print(f"{lanc} Meta FALHOU: {e}")
    conta, lista = cfg["google"]
    if not (forcar_google or google_pode_ingerir(cfg, hoje)):
        print(f"{lanc} Google {lista}: criada hoje, ingestão fica para amanhã (VER-5)")
        return ok
    try:
        ids = atualizar_google(Google(), conta, lista, pessoas, lanc)
        print(f"{lanc} Google {lista}: {len(pessoas)} pessoas em {len(ids)} lote(s); request_ids: {' '.join(ids)}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"{lanc} Google FALHOU: {e}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lancamentos", nargs="*")
    ap.add_argument("--ativos", action="store_true", help="todos de padroes.LISTAS_CADASTRADOS até a data 'ate'")
    ap.add_argument("--criar", action="store_true", help="cria as listas dos lançamentos informados")
    ap.add_argument("--status", nargs="+", metavar="REQUEST_ID", help="status dos pedidos do Google")
    a = ap.parse_args()
    if a.status:
        from scripts.ads.google import Google
        for s in Google().status_pedidos(a.status):
            print(s)
        return 0
    if a.criar:
        for lanc in a.lancamentos:
            criar(lanc.upper())
        return 0
    hoje = dt.date.today()
    alvo = lancamentos_ativos(P.LISTAS_CADASTRADOS, hoje) if a.ativos else [x.upper() for x in a.lancamentos]
    if not alvo:
        print("Nenhum lançamento com lista de cadastrados ativa.")
        return 0
    falhas = [lanc for lanc in alvo if lanc not in P.LISTAS_CADASTRADOS
              or not atualizar(lanc, P.LISTAS_CADASTRADOS[lanc], hoje, forcar_google=not a.ativos)]
    for lanc in falhas:
        print(f"FALHA: {lanc}" + ("" if lanc in P.LISTAS_CADASTRADOS else " (fora de padroes.LISTAS_CADASTRADOS)"))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
