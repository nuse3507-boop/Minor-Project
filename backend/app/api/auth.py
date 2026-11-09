import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import delete, select

from app.config import settings
from app.models import AuthToken, Session, Source, User, now
from app.schemas import AccountInput, Credentials, EmailRequest, ProfileResponse, TokenRequest
from app.security import CurrentUser, Db, create_session, digest, hasher, password_valid, throttle
from app.services.resources import audit, delete_source, flush_storage_deletions, source_dict

router = APIRouter()


def profile(user, csrf):
    return {
        "id": user.id,
        "email": user.email,
        "is_guest": user.is_guest,
        "csrf_token": csrf,
        "retention_days": user.retention_days,
        "preferred_provider": user.preferred_provider,
        "verified": user.verified_at is not None,
        "providers": [
            {"name": p["name"], "model": p["model"], "configured": bool(p["key"] and p["model"])}
            for p in settings().providers()
        ],
    }


def send_token(db, user, purpose):
    cfg = settings()
    if not cfg.smtp_host or not cfg.mail_from:
        raise HTTPException(503, "Email delivery is not configured. Contact the deployment administrator.")
    token = secrets.token_urlsafe(32)
    db.execute(delete(AuthToken).where(AuthToken.user_id == user.id, AuthToken.purpose == purpose))
    db.add(
        AuthToken(id=digest(token), user_id=user.id, purpose=purpose, expires_at=now() + timedelta(hours=1))
    )
    message = EmailMessage()
    message["From"] = cfg.mail_from
    message["To"] = user.email
    message["Subject"] = (
        "Veriora account verification" if purpose == "verify" else "Veriora password recovery"
    )
    message.set_content(
        f"Open {cfg.public_url}/sign-in?purpose={purpose}&token={token}\nThis link expires in one hour."
    )
    try:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if cfg.smtp_user:
                smtp.login(cfg.smtp_user, cfg.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise HTTPException(503, "Email could not be delivered. Please try again later.") from None


@router.get("/me", response_model=ProfileResponse)
def me(request: Request, user: CurrentUser):
    return profile(user, request.state.session.csrf)


@router.post("/auth/guest", status_code=201, response_model=ProfileResponse)
def guest(request: Request, response: Response, db: Db):
    cookie = request.cookies.get("veriora_session")
    existing = db.get(Session, digest(cookie)) if cookie else None
    if existing and existing.expires_at.replace(tzinfo=now().tzinfo) > now():
        current = db.get(User, existing.user_id)
        if current:
            return profile(current, existing.csrf)
    throttle(db, "guest:" + (request.client.host if request.client else "unknown"), 5, 3600)
    user = User(is_guest=True, retention_days=1)
    db.add(user)
    db.flush()
    record = create_session(db, user, response)
    db.commit()
    return profile(user, record.csrf)


@router.post("/auth/register", status_code=201, response_model=ProfileResponse)
def register(data: Credentials, request: Request, response: Response, db: Db):
    throttle(db, "register:" + (request.client.host if request.client else "unknown"), 5, 3600)
    email = str(data.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "This account cannot be registered. Try signing in or recovering access.")
    if settings().environment == "production" and not settings().smtp_host:
        raise HTTPException(503, "Account registration requires configured email verification.")
    prior_cookie = request.cookies.get("veriora_session")
    prior_session = db.get(Session, digest(prior_cookie)) if prior_cookie else None
    prior_user = db.get(User, prior_session.user_id) if prior_session else None
    if prior_user and prior_user.is_guest and prior_session.expires_at.replace(tzinfo=now().tzinfo) > now():
        if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), prior_session.csrf):
            raise HTTPException(403, "Reload your guest session before creating an account.")
        user = prior_user
        user.email, user.password_hash, user.is_guest = email, hasher.hash(data.password), False
        user.retention_days = 30
        for source in db.scalars(select(Source).where(Source.owner_id == user.id, Source.expires_at > now())):
            source.expires_at = source.captured_at.replace(tzinfo=now().tzinfo) + timedelta(days=30)
        db.delete(prior_session)
    else:
        user = User(email=email, password_hash=hasher.hash(data.password))
        db.add(user)
    db.flush()
    if settings().smtp_host:
        send_token(db, user, "verify")
    else:
        # Local development only; production startup and registration enforce delivery.
        user.verified_at = now()
    record = create_session(db, user, response)
    audit(db, user.id, "account.registered", user.id)
    db.commit()
    return profile(user, record.csrf)


@router.post("/auth/login", response_model=ProfileResponse)
def login(data: Credentials, request: Request, response: Response, db: Db):
    throttle(db, "login-ip:" + (request.client.host if request.client else "unknown"), 20, 900)
    throttle(db, "login-email:" + str(data.email).lower(), 10, 900)
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    # Hash unknown passwords too, avoiding a fast account-enumeration path.
    encoded = user.password_hash if user else hasher.hash(secrets.token_urlsafe(24))
    if not password_valid(encoded, data.password) or not user:
        raise HTTPException(401, "Email or password is incorrect.")
    prior = request.cookies.get("veriora_session")
    if prior:
        db.execute(delete(Session).where(Session.id == digest(prior)))
    record = create_session(db, user, response)
    db.commit()
    return profile(user, record.csrf)


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Db, user: CurrentUser):
    db.delete(request.state.session)
    db.commit()
    response.delete_cookie("veriora_session", path="/")


@router.post("/auth/recover")
def recover(data: EmailRequest, request: Request, db: Db):
    throttle(db, "recover:" + (request.client.host if request.client else "unknown"), 5, 900)
    if not settings().smtp_host:
        raise HTTPException(503, "Email recovery is not configured. Contact the deployment administrator.")
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if user:
        send_token(db, user, "recover")
        db.commit()
    return {"message": "If an account exists, recovery instructions will be sent."}


@router.post("/auth/verify")
def verify_email(data: TokenRequest, db: Db):
    token = db.scalar(select(AuthToken).where(AuthToken.id == digest(data.token)).with_for_update())
    if not token or token.purpose != "verify" or token.expires_at.replace(tzinfo=now().tzinfo) <= now():
        raise HTTPException(400, "Verification link is invalid or expired.")
    db.get(User, token.user_id).verified_at = now()
    db.delete(token)
    db.commit()
    return {"message": "Email verified."}


@router.post("/auth/reset")
def reset_password(data: TokenRequest, db: Db):
    token = db.scalar(select(AuthToken).where(AuthToken.id == digest(data.token)).with_for_update())
    if (
        not data.password
        or not token
        or token.purpose != "recover"
        or token.expires_at.replace(tzinfo=now().tzinfo) <= now()
    ):
        raise HTTPException(400, "Recovery link is invalid or expired.")
    db.get(User, token.user_id).password_hash = hasher.hash(data.password)
    db.execute(delete(Session).where(Session.user_id == token.user_id))
    db.delete(token)
    db.commit()
    return {"message": "Password updated. Sign in again."}


@router.patch("/me")
def update_account(data: AccountInput, request: Request, db: Db, user: CurrentUser):
    if user.is_guest:
        raise HTTPException(403, "Create an account to save settings.")
    user.retention_days = data.retention_days
    user.preferred_provider = data.preferred_provider
    # Shortening retention applies immediately to retained sources.
    for source in db.scalars(select(Source).where(Source.owner_id == user.id)):
        new_expiry = source.captured_at.replace(tzinfo=now().tzinfo) + timedelta(days=data.retention_days)
        if new_expiry < source.expires_at.replace(tzinfo=now().tzinfo):
            source.expires_at = new_expiry
    db.commit()
    return profile(user, request.state.session.csrf)


@router.get("/me/export")
def export_account(db: Db, user: CurrentUser):
    if user.is_guest:
        raise HTTPException(403, "Create an account to export retained data.")
    sources = db.scalars(select(Source).where(Source.owner_id == user.id, Source.expires_at > now())).all()
    return {
        "account": {"id": user.id, "email": user.email, "retention_days": user.retention_days},
        "sources": [source_dict(s) for s in sources],
        "notice": "Download individual source originals and analysis manifests from your library.",
    }


@router.delete("/me", status_code=204)
def delete_account(response: Response, db: Db, user: CurrentUser):
    for source in db.scalars(select(Source).where(Source.owner_id == user.id)).all():
        delete_source(db, source)
    audit(db, user.id, "account.deleted", user.id)
    db.delete(user)
    db.commit()
    flush_storage_deletions(db)
    response.delete_cookie("veriora_session", path="/")
