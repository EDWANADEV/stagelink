from __future__ import annotations

import datetime
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from stagelink.users.models import Otp
from stagelink.users.otp_utils import check_cooldown
from stagelink.users.otp_utils import create_otp_token
from stagelink.users.otp_utils import generate_otp_code
from stagelink.users.otp_utils import hash_otp_code
from stagelink.users.otp_utils import set_cooldown
from stagelink.users.otp_utils import validate_otp_token
from stagelink.users.tasks import send_otp_email_task
from stagelink.utils.enums import OtpPurpose


class OtpRateLimitError(ValueError):
    pass


class OtpVerificationError(ValueError):
    pass


class OtpService:
    @staticmethod
    def create(user, purpose: str) -> tuple[Otp, str]:
        limited, _remaining = check_cooldown(str(user.pk), purpose)
        if limited:
            raise OtpRateLimitError(_("Veuillez patienter avant de demander un nouveau code."))

        validity = getattr(settings, "OTP_VALID_MINUTES", 10)
        raw_code = generate_otp_code()
        expiration_at = timezone.now() + datetime.timedelta(minutes=validity)

        with transaction.atomic():
            Otp.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
            otp = Otp.objects.create(
                user=user,
                purpose=purpose,
                code_hash=hash_otp_code(raw_code),
                expiration_at=expiration_at,
            )
            set_cooldown(str(user.pk), purpose)

        otp._raw_code = raw_code  # noqa: SLF001
        token = create_otp_token(str(otp.pk), str(user.pk), purpose)
        return otp, token


class OtpEmailService:
    @staticmethod
    def send(user, otp: Otp, language: str | None = None) -> None:
        raw_code = getattr(otp, "_raw_code", None)
        if not raw_code:
            msg = "Raw OTP code is required."
            raise ValueError(msg)

        full_name = str(user) or user.email
        validity = getattr(settings, "OTP_VALID_MINUTES", 10)
        lang = language or getattr(user, "language", None) or settings.LANGUAGE_CODE

        transaction.on_commit(
            lambda: send_otp_email_task.delay(
                email=user.email,
                full_name=full_name,
                code=raw_code,
                validity=validity,
                language=lang,
            ),
        )


class OtpVerifyService:
    @staticmethod
    def _resolve_otp(token: str, purpose: str) -> Otp:
        token_data = validate_otp_token(token, purpose)
        try:
            return Otp.objects.select_for_update().select_related("user").get(
                pk=token_data["otp_id"],
                user_id=token_data["user_id"],
                purpose=purpose,
            )
        except Otp.DoesNotExist as err:
            raise OtpVerificationError(_("Ce code de vérification est introuvable.")) from err

    @staticmethod
    def verify(token: str, code: str, purpose: str) -> Otp:
        with transaction.atomic():
            otp = OtpVerifyService._resolve_otp(token, purpose)
            if otp.is_used or otp.is_expired():
                raise OtpVerificationError(_("Ce code a expiré. Demandez un nouveau code."))
            if not otp.can_attempt():
                raise OtpVerificationError(_("Trop de tentatives. Demandez un nouveau code."))

            otp.increment_attempts()
            if not otp.is_valid_code(code):
                raise OtpVerificationError(_("Le code saisi est incorrect."))

            otp.mark_verified()
            if purpose in {OtpPurpose.SIGNUP, OtpPurpose.LOGIN}:
                user = otp.user
                user.is_verified = True
                user.save(update_fields=["is_verified"])
            return otp


class PasswordResetTokenService:
    timeout = getattr(settings, "RESET_TOKEN_TIMEOUT", 15) * 60

    @staticmethod
    def generate(user) -> str:
        token = str(uuid.uuid4())
        cache.set(f"password_reset_token:{token}", str(user.pk), timeout=PasswordResetTokenService.timeout)
        return token

    @staticmethod
    def get_user_id(token: str) -> str | None:
        if not token:
            return None
        return cache.get(f"password_reset_token:{token}")

    @staticmethod
    def delete(token: str) -> None:
        cache.delete(f"password_reset_token:{token}")