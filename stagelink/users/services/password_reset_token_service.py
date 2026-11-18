from __future__ import annotations

import secrets

from django.conf import settings
from django.core.cache import cache

from stagelink.users.models import User


class PasswordResetTokenService:
    """Service responsible for password reset tokens."""

    timeout = getattr(
        settings,
        "RESET_TOKEN_TIMEOUT",
        15,
    ) * 60

    @classmethod
    def generate(
        cls,
        user: User,
    ) -> str:
        token = secrets.token_urlsafe(32)

        cache.set(
            f"password_reset_token:{token}",
            str(user.pk),
            timeout=cls.timeout,
        )

        return token

    @classmethod
    def get_user_id(
        cls,
        token: str,
    ) -> str | None:
        if not token:
            return None

        return cache.get(
            f"password_reset_token:{token}",
        )

    @classmethod
    def delete(
        cls,
        token: str,
    ) -> None:
        cache.delete(
            f"password_reset_token:{token}",
        )