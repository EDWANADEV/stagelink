from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

_TOKEN_SEP = ":"


class OtpTokenError(ValueError):
    """Raised when an OTP token cannot be used."""


class OtpTokenExpiredError(OtpTokenError):
    """Raised when an OTP token is expired."""


def generate_otp_code(length: int = 6) -> str:
    """
    Génère un code OTP numérique sécurisé.

    La longueur minimale est de 4 chiffres.
    """

    length = max(length, 4)
    upper_bound = 10**length

    return f"{secrets.randbelow(upper_bound):0{length}d}"


def hash_otp_code(code: str) -> str:
    """
    Hache un code OTP avant son stockage en base de données.
    """

    return make_password(code)


def verify_otp_code(code: str, hashed: str) -> bool:
    """
    Vérifie un code OTP par rapport à son hachage.
    """

    if not hashed:
        return False

    return check_password(code, hashed)


def create_otp_token(
    otp_id: str,
    user_id: str,
    purpose: str,
) -> str:
    """
    Crée un token signé contenant les informations
    nécessaires pour identifier une vérification OTP.
    """

    payload = _TOKEN_SEP.join(
        [
            str(otp_id),
            str(user_id),
            purpose,
        ]
    )

    signer = TimestampSigner(
        salt=f"otp-token-{purpose}",
    )

    return signer.sign(payload)


def decode_otp_token(
    signed_token: str,
    purpose: str,
) -> dict[str, str]:
    """
    Décode un token OTP signé sans vérifier sa durée de validité.

    Cette fonction est destinée aux opérations qui doivent pouvoir
    identifier une vérification OTP même après expiration du token,
    notamment le renvoi d'un nouveau code.

    La signature et le purpose restent obligatoirement vérifiés.
    """

    signer = TimestampSigner(
        salt=f"otp-token-{purpose}",
    )

    try:
        payload = signer.unsign(signed_token)
    except BadSignature as error:
        raise OtpTokenError(
            "Le lien de vérification est invalide."
        ) from error

    parts = payload.split(_TOKEN_SEP)

    if len(parts) != 3:
        raise OtpTokenError(
            "Le lien de vérification est invalide."
        )

    otp_id, user_id, embedded_purpose = parts

    if embedded_purpose != purpose:
        raise OtpTokenError(
            "Ce code ne correspond pas à cette opération."
        )

    return {
        "otp_id": otp_id,
        "user_id": user_id,
        "purpose": purpose,
    }


def validate_otp_token(
    signed_token: str,
    purpose: str,
) -> dict[str, str]:
    """
    Vérifie et décode un token OTP signé.
    """

    max_age = getattr(
        settings,
        "OTP_VALID_MINUTES",
        10,
    ) * 60

    signer = TimestampSigner(
        salt=f"otp-token-{purpose}",
    )

    try:
        payload = signer.unsign(
            signed_token,
            max_age=max_age,
        )
    except SignatureExpired as error:
        raise OtpTokenExpiredError(
            "Le lien de vérification a expiré."
        ) from error
    except BadSignature as error:
        raise OtpTokenError(
            "Le lien de vérification est invalide."
        ) from error

    parts = payload.split(_TOKEN_SEP)

    if len(parts) != 3:
        raise OtpTokenError(
            "Le lien de vérification est invalide."
        )

    otp_id, user_id, embedded_purpose = parts

    if embedded_purpose != purpose:
        raise OtpTokenError(
            "Ce code ne correspond pas à cette opération."
        )

    return {
        "otp_id": otp_id,
        "user_id": user_id,
        "purpose": purpose,
    }


def _cooldown_key(
    user_id: str,
    purpose: str,
) -> str:
    """
    Génère la clé de cache utilisée pour limiter
    les demandes successives d'OTP.
    """

    return f"otp_cooldown:{purpose}:{user_id}"


def check_cooldown(
    user_id: str,
    purpose: str,
) -> tuple[bool, int]:
    """
    Vérifie si l'utilisateur doit attendre avant
    de demander un nouvel OTP.

    Retourne :
        (True, secondes_restantes)
        ou
        (False, 0)
    """

    key = _cooldown_key(user_id, purpose)

    remaining = cache.ttl(key) if hasattr(cache, "ttl") else None

    if remaining is not None and remaining > 0:
        return True, remaining

    if cache.get(key):
        return True, getattr(
            settings,
            "OTP_REQUEST_COOLDOWN_SECONDS",
            60,
        )

    return False, 0


def set_cooldown(
    user_id: str,
    purpose: str,
) -> None:
    """
    Active le délai avant une nouvelle demande d'OTP.
    """

    timeout = getattr(
        settings,
        "OTP_REQUEST_COOLDOWN_SECONDS",
        60,
    )

    cache.set(
        _cooldown_key(user_id, purpose),
        value=True,
        timeout=timeout,
    )