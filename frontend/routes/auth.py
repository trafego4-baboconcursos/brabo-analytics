from __future__ import annotations
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from frontend.core import (
    templates, logger, BRABO_USER, BRABO_PASS, ROLE_LABELS, PRODUCT_LABELS,
    COOKIE_SECURE, _check_login_rate_limit, _record_login_attempt,
    _verify_password, _hash_password, _set_session_cookie,
    get_user_by_email, update_last_login, create_user,
    get_invite, use_invite,
)

router = APIRouter()


@router.get("/login")
def login_page(request: Request, next: str | None = None, invited: str | None = None):
    return templates.TemplateResponse("login.html", {
        "request": request, "error": None, "next_launch": next, "invited": invited,
    })


@router.post("/login")
def login_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next_launch: str | None = Form(None),
):
    client_ip = request.client.host if request.client else "unknown"

    if not _check_login_rate_limit(client_ip):
        logger.warning("Rate limit de login atingido para IP %s", client_ip)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Muitas tentativas. Aguarde alguns minutos.", "next_launch": next_launch},
        )

    user_record = None
    try:
        user_record = get_user_by_email(email)
        if user_record and user_record.get("is_active") and _verify_password(password, user_record["password_hash"]):
            update_last_login(user_record["id"])
            response = RedirectResponse(url=next_launch or "/", status_code=303)
            _set_session_cookie(
                response,
                user_id=user_record["id"],
                role=user_record["role"],
                products=user_record.get("products", ["ALL"]),
                email=user_record["email"],
            )
            return response
    except Exception:
        logger.exception("Erro na autenticação via banco; usando fallback")

    if email == BRABO_USER and password == BRABO_PASS:
        response = RedirectResponse(url=next_launch or "/", status_code=303)
        _set_session_cookie(response, "legacy", "admin", ["ALL"], BRABO_USER)
        return response

    _record_login_attempt(client_ip)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "E-mail ou senha inválidos.", "next_launch": next_launch},
    )


@router.get("/logout")
def logout_action():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="session_token", samesite="lax", secure=COOKIE_SECURE)
    return response


@router.get("/invite/{token}")
def invite_page(request: Request, token: str):
    invite = get_invite(token)
    error = None
    if not invite:
        error = "Link de convite inválido ou não encontrado."
    elif invite["is_used"]:
        error = "Este link de convite já foi utilizado."
    elif invite["is_expired"]:
        error = "Este link de convite expirou."
    return templates.TemplateResponse("invite.html", {
        "request": request, "invite": invite, "error": error, "token": token,
        "role_labels": ROLE_LABELS, "product_labels": PRODUCT_LABELS,
    })


@router.post("/invite/{token}")
def invite_action(
    request: Request,
    token: str,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    invite = get_invite(token)
    ctx_base = {"request": request, "invite": invite, "token": token,
                "role_labels": ROLE_LABELS, "product_labels": PRODUCT_LABELS}

    if not invite or invite["is_used"] or invite["is_expired"]:
        return templates.TemplateResponse("invite.html", {**ctx_base, "error": "Convite inválido ou expirado."})
    if password != confirm_password:
        return templates.TemplateResponse("invite.html", {**ctx_base, "error": "As senhas não coincidem."})
    if len(password) < 8:
        return templates.TemplateResponse("invite.html", {**ctx_base, "error": "A senha deve ter ao menos 8 caracteres."})

    try:
        existing = get_user_by_email(email)
        if existing:
            return templates.TemplateResponse("invite.html", {**ctx_base, "error": "Este e-mail já está cadastrado."})
        user_id = create_user(
            email=email,
            name=name,
            password_hash=_hash_password(password),
            role=invite["role"],
            products=invite["products"],
        )
        use_invite(token, user_id)
        return RedirectResponse(url="/login?invited=1", status_code=303)
    except Exception as exc:
        return templates.TemplateResponse("invite.html", {**ctx_base, "error": f"Erro ao criar conta: {exc}"})
