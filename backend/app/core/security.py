import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        headers={"kid": settings.jwt_active_kid},
    )


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh", "jti": uuid.uuid4().hex})
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        headers={"kid": settings.jwt_active_kid},
    )


def decode_token(token: str) -> dict | None:
    try:
        unverified_headers = jwt.get_unverified_header(token)
    except JWTError:
        return None

    token_kid = str(unverified_headers.get("kid", "")).strip()
    secrets_to_try: list[str] = []

    if token_kid == settings.jwt_active_kid:
        secrets_to_try.append(settings.jwt_secret_key)
    elif settings.jwt_previous_secret_key and token_kid == settings.jwt_previous_kid:
        secrets_to_try.append(settings.jwt_previous_secret_key)
    else:
        # Fallback strategy for old tokens without kid or unknown kid.
        secrets_to_try.append(settings.jwt_secret_key)
        if settings.jwt_previous_secret_key:
            secrets_to_try.append(settings.jwt_previous_secret_key)

    tried = set()
    for secret in secrets_to_try:
        if not secret or secret in tried:
            continue
        tried.add(secret)
        try:
            payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
            return payload
        except JWTError:
            continue

    return None
