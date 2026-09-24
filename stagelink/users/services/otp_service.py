from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from stagelink.users.models import OTPVerification, User
from stagelink.users.otp_utils import (
    check_cooldown,
    create_otp_token,
    generate_otp_code,
    hash_otp_code,
    set_cooldown,
    validate_otp_token,
    verify_otp_code,
)


class OtpRateLimitError(ValueError):
    """Raised when an OTP request is rate-limited."""


class OtpVerificationError(ValueError):
    """Raised when an OTP verification fails."""


class OtpService:
    """Service responsible for creating OTP codes."""

    @staticmethod
    def create(
        user: User,
        otp_type: str,
    ) -> tuple[OTPVerification, str]:
        limited, _remaining = check_cooldown(
            str(user.pk),
            otp_type,
        )

        if limited:
            raise OtpRateLimitError(
                _(
                    "Veuillez patienter avant de demander "
                    "un nouveau code."
                )
            )

        validity = getattr(
            settings,
            "OTP_VALID_MINUTES",
            10,
        )

        raw_code = generate_otp_code()

        expires_at = timezone.now() + timedelta(
            minutes=validity,
        )

        with transaction.atomic():
            OTPVerification.objects.filter(
                user=user,
                otp_type=otp_type,
                is_used=False,
            ).update(is_used=True)

            otp = OTPVerification.objects.create(
                user=user,
                otp_type=otp_type,
                code=hash_otp_code(raw_code),
                expires_at=expires_at,
            )

            set_cooldown(
                str(user.pk),
                otp_type,
            )

        # Le code brut existe uniquement en mémoire.
        otp._raw_code = raw_code

        token = create_otp_token(
            str(otp.pk),
            str(user.pk),
            otp_type,
        )

        return otp, token


class OtpVerifyService:
    """Service responsible for verifying OTP codes."""

    @staticmethod
    def _resolve_otp(
        token: str,
        otp_type: str,
    ) -> OTPVerification:
        token_data = validate_otp_token(
            token,
            otp_type,
        )

        try:
            return (
                OTPVerification.objects
                .select_for_update()
                .select_related("user")
                .get(
                    pk=token_data["otp_id"],
                    user_id=token_data["user_id"],
                    otp_type=otp_type,
                )
            )
        except OTPVerification.DoesNotExist as error:
            raise OtpVerificationError(
                _("Cette vérification est introuvable.")
            ) from error

    @staticmethod
    def verify(
        token: str,
        code: str,
        otp_type: str,
    ) -> OTPVerification:
        with transaction.atomic():
            otp = OtpVerifyService._resolve_otp(
                token,
                otp_type,
            )

            if otp.is_used:
                raise OtpVerificationError(
                    _("Ce code a déjà été utilisé.")
                )

            if timezone.now() > otp.expires_at:
                raise OtpVerificationError(
                    _(
                        "Ce code a expiré. "
                        "Demandez un nouveau code."
                    )
                )

            max_attempts = getattr(
                settings,
                "OTP_MAX_ATTEMPTS",
                5,
            )

            if otp.attempts >= max_attempts:
                raise OtpVerificationError(
                    _(
                        "Trop de tentatives. "
                        "Demandez un nouveau code."
                    )
                )

            otp.attempts += 1

            otp.save(
                update_fields=[
                    "attempts",
                    "updated_at",
                ]
            )

            if not verify_otp_code(
                code,
                otp.code,
            ):
                raise OtpVerificationError(
                    _("Le code saisi est incorrect.")
                )

            otp.is_used = True

            otp.save(
                update_fields=[
                    "is_used",
                    "updated_at",
                ]
            )

            return otp