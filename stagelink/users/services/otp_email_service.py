from __future__ import annotations

from django.conf import settings
from django.db import transaction

from stagelink.users.models import OTPVerification, User
from stagelink.users.tasks import send_otp_email_task


class OtpEmailService:
    """Service responsible for sending OTP emails."""

    @staticmethod
    def send(
        user: User,
        otp: OTPVerification,
        language: str | None = None,
    ) -> None:
        raw_code = getattr(
            otp,
            "_raw_code",
            None,
        )

        if not raw_code:
            raise ValueError(
                "Le code OTP brut est nécessaire "
                "pour envoyer l'e-mail."
            )

        validity = settings.OTP_EXPIRATION_MINUTES

        lang = language or settings.LANGUAGE_CODE
        full_name = user.name or user.email

        transaction.on_commit(
            lambda: send_otp_email_task.delay(
                email=user.email,
                full_name=full_name,
                code=raw_code,
                validity=validity,
                otp_type=otp.otp_type,
                language=lang,
            )
        )