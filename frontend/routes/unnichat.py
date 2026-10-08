from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from frontend.services.unnichat import banco, coletor

router = APIRouter()


@router.post("/api/unnichat/webhook/{conexao}")
async def unnichat_webhook(conexao: str, request: Request, x_webhook_secret: str = Header(None)):
    """Chamado pela automação do Unnichat de cada conta. Fora do login do site
    (ver auth_middleware); autenticado pelo header X-Webhook-Secret."""
    segredo = coletor.segredo_webhook()
    if not segredo or not x_webhook_secret or not secrets.compare_digest(x_webhook_secret, segredo):
        raise HTTPException(status_code=401, detail="unauthorized")
    conexao = conexao.lower()
    if conexao not in coletor.tokens():
        raise HTTPException(status_code=400, detail=f"conta desconhecida ou sem token: {conexao}")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="payload não é JSON")
    # Mesmo formato que a automação já manda pro backup: o contato vem solto
    # no corpo ou dentro de "contact"/"data", conforme o gatilho.
    contato = (body.get("contact") or body.get("data") or body) if isinstance(body, dict) else {}
    contact_id = contato.get("id") or (body.get("contactId") if isinstance(body, dict) else None)
    if not contact_id:
        raise HTTPException(status_code=400, detail="contactId ausente")
    novos = await run_in_threadpool(banco.enfileirar, [{
        "conexao": conexao, "contact_id": str(contact_id),
        "telefone": contato.get("phoneNumber") or contato.get("phone"), "nome": contato.get("name"),
    }], "webhook")
    return {"ok": True, "enfileirado": bool(novos)}


@router.get("/api/unnichat/status")
def unnichat_status():
    """Saúde do coletor (só admin, ver ROUTE_PERMISSIONS)."""
    return {"contas": sorted(coletor.tokens()), **coletor.ESTADO}
