from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.signing import BadSignature
from django.core.signing import SignatureExpired
from django.core.signing import TimestampSigner

_TOKEN_SEP = ":"  # noqa: S105


class OtpTokenError(ValueError):
    """Raised when an OTP token cannot be used."""


class OtpTokenExpiredError(OtpTokenError):
    """Raised when an OTP token is expired."""


def generate_otp_code(length: int = 6) -> str:
    """Génère un code OTP numérique du nombre de chiffres demandé."""
    length = max(length, 4)
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


def hash_otp_code(code: str) -> str:
    """Hache un code OTP en clair à l'aide du hacheur de mots de passe de Django."""
    return make_password(code)


def verify_otp_code(code: str, hashed: str) -> bool:
    """Vérifie qu'un code OTP correspond au hachage stocké."""
    if not hashed:
        return False
    return check_password(code, hashed)


def create_otp_token(otp_id: str, user_id: str, purpose: str) -> str:
    payload = _TOKEN_SEP.join([str(otp_id), str(user_id), purpose])
    signer = TimestampSigner(salt=f"otp-token-{purpose}")
    return signer.sign(payload)


def validate_otp_token(signed_token: str, purpose: str) -> dict[str, str]:
    max_age = getattr(settings, "OTP_VALID_MINUTES", 10) * 60
    signer = TimestampSigner(salt=f"otp-token-{purpose}")

    try:
        payload = signer.unsign(signed_token, max_age=max_age)
    except SignatureExpired as err:
        msg = "Le code de vérification a expiré."
        raise OtpTokenExpiredError(msg) from err
    except BadSignature as err:
        msg = "Le lien de vérification est invalide."
        raise OtpTokenError(msg) from err

    parts = payload.split(_TOKEN_SEP)
    if len(parts) != 3:  # noqa: PLR2004
        msg = "Le lien de vérification est invalide."
        raise OtpTokenError(msg)

    otp_id, user_id, embedded_purpose = parts
    if embedded_purpose != purpose:
        msg = "Ce code ne correspond pas à cette opération."
        raise OtpTokenError(msg)

    return {"otp_id": otp_id, "user_id": user_id, "purpose": purpose}


def _cooldown_key(user_id: str, purpose: str) -> str:
    return f"otp_cooldown:{purpose}:{user_id}"


def check_cooldown(user_id: str, purpose: str) -> tuple[bool, int]:
    key = _cooldown_key(user_id, purpose)
    remaining = cache.ttl(key) if hasattr(cache, "ttl") else None
    if remaining is not None and remaining > 0:
        return True, remaining
    if cache.get(key):
        return True, getattr(settings, "OTP_REQUEST_COOLDOWN_SECONDS", 60)
    return False, 0


def set_cooldown(user_id: str, purpose: str) -> None:
    timeout = getattr(settings, "OTP_REQUEST_COOLDOWN_SECONDS", 60)
    cache.set(_cooldown_key(user_id, purpose), value=True, timeout=timeout)