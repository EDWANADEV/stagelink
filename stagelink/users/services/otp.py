import secrets
from datetime import timedelta
from django.db import transaction

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from stagelink.users.models import OTPVerification
from stagelink.users.models import User
from stagelink.users.tasks import send_otp_email


class OTPService:
    """Service responsable de la gestion des codes OTP."""

    @staticmethod
    def generate_code() -> str:
        """Génère un code OTP numérique sécurisé."""
        upper_bound = 10**settings.OTP_LENGTH

        return str(
            secrets.randbelow(upper_bound),
        ).zfill(settings.OTP_LENGTH)

    @classmethod
    def create_otp(
        cls,
        user: User,
        otp_type: str,
    ) -> tuple[OTPVerification, str]:
        """Crée un nouveau code OTP et l'enregistre sous forme de hash."""
        OTPVerification.objects.filter(
            user=user,
            otp_type=otp_type,
            is_used=False,
        ).update(
            is_used=True,
        )

        code = cls.generate_code()

        expires_at = timezone.now() + timedelta(
            minutes=settings.OTP_EXPIRATION_MINUTES,
        )

        verification = OTPVerification.objects.create(
            user=user,
            code=make_password(code),
            otp_type=otp_type,
            expires_at=expires_at,
        )

        return verification, code

    @staticmethod
    def verify_code(
        verification: OTPVerification,
        code: str,
    ) -> bool:
        """Vérifie un code OTP."""
        if verification.is_used:
            return False

        if verification.expires_at <= timezone.now():
            return False

        if verification.attempts >= settings.OTP_MAX_ATTEMPTS:
            return False

        verification.attempts += 1

        if check_password(code, verification.code):
            verification.is_used = True
            verification.save(
                update_fields=[
                    "attempts",
                    "is_used",
                    "updated_at",
                ],
            )
            return True

        verification.save(
            update_fields=[
                "attempts",
                "updated_at",
            ],
        )

        return False

    @classmethod
    def verify_otp(
        cls,
        user: User,
        code: str,
        otp_type: str,
    ) -> tuple[bool, str]:
        """Vérifie le dernier code OTP actif de l'utilisateur."""
        verification = (
            OTPVerification.objects.filter(
                user=user,
                otp_type=otp_type,
                is_used=False,
            )
            .order_by("-created_at")
            .first()
        )

        if verification is None:
            return False, _("Aucun code actif. Demandez un nouveau code.")

        if verification.expires_at <= timezone.now():
            return False, _("Ce code a expiré. Demandez un nouveau code.")

        if verification.attempts >= settings.OTP_MAX_ATTEMPTS:
            return False, _(
                "Nombre maximal de tentatives atteint. Demandez un nouveau code.",
            )

        if not cls.verify_code(verification, code):
            return False, _("Le code saisi est incorrect.")

        return True, _("Code vérifié.")

    @staticmethod
    def can_resend(user: User, otp_type: str) -> bool:
        """Empêche l'envoi répété de codes dans un court intervalle."""
        cooldown_start = timezone.now() - timedelta(
            seconds=settings.OTP_REQUEST_COOLDOWN_SECONDS,
        )

        return not OTPVerification.objects.filter(
            user=user,
            otp_type=otp_type,
            created_at__gte=cooldown_start,
        ).exists()

    @staticmethod
    def send_otp(
        verification: OTPVerification,
        code: str,
        ) -> None:
        """Planifie l'envoi du code OTP après validation de la transaction."""
        transaction.on_commit(
            lambda: send_otp_email.delay(
                str(verification.id),
                code,
            ),
        )