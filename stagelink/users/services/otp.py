
from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from stagelink.utils.email import EmailUtil
from stagelink.users.models import OTPVerification


class OTPService:
    """Service responsable de générer, vérifier, et envoyer les codes"""

    DEFAULT_EXPIRATION_MINUTES = 10
    MAX_ATTEMPTS = 5

    @classmethod
    def _get_expiration_minutes(cls) -> int:
        return getattr(
            settings,
            "OTP_EXPIRATION_MINUTES",
            cls.DEFAULT_EXPIRATION_MINUTES,
        )

    @classmethod
    def _generate_code(cls) -> str:
        """Generate a cryptographically secure six-digit OTP."""
        return f"{secrets.randbelow(1_000_000):06d}"

    @classmethod
    @transaction.atomic
    def create_otp(
        cls,
        user,
        otp_type: str,
    ) -> OTPVerification:
        """Créer un nouveau code OTP pour un utilisateur.
        Les codes OTP existants du même type et non utilisés sont invalidés en premier.
        """
        OTPVerification.objects.filter(
            user=user,
            otp_type=otp_type,
            is_used=False,
        ).update(is_used=True)

        expiration_minutes = cls._get_expiration_minutes()

        otp = OTPVerification.objects.create(
            user=user,
            code=cls._generate_code(),
            otp_type=otp_type,
            expires_at=timezone.now()
            + timedelta(minutes=expiration_minutes),
        )

        return otp

    @classmethod
    def send_otp(
        cls,
        user,
        otp_type: str,
    ) -> OTPVerification:
        """Generate an OTP and send it to the user's email."""
        otp = cls.create_otp(
            user=user,
            otp_type=otp_type,
        )

        if otp_type == OTPVerification.OTPType.SIGNUP:
            subject = _("Vérifiez votre adresse e-mail")
            template = "emails/otp/signup.html"
        elif otp_type == OTPVerification.OTPType.PASSWORD_RESET:
            subject = _("Réinitialisation de votre mot de passe")
            template = "emails/otp/password_reset.html"
        else:
            raise ValueError(
                f"Unsupported OTP type: {otp_type}",
            )

        success = EmailUtil.send_email_with_template(
            template=template,
            context={
                "user": user,
                "otp_code": otp.code,
                "expires_at": otp.expires_at,
            },
            receivers=[user.email],
            subject=subject,
            language=getattr(
                user,
                "language",
                None,
            ),
        )

        if not success:
            otp.delete()
            raise RuntimeError(
                _("Impossible d'envoyer le code de vérification."),
            )

        return otp

    @classmethod
    def verify_otp(
        cls,
        user,
        code: str,
        otp_type: str,
    ) -> tuple[bool, str]:
        """
        Verify an OTP code.

        Returns:
            (success, message)
        """
        otp = (
            OTPVerification.objects.filter(
                user=user,
                otp_type=otp_type,
                is_used=False,
            )
            .order_by("-created_at")
            .first()
        )

        if otp is None:
            return False, str(
                _("Aucun code de vérification valide n'a été trouvé."),
            )

        if timezone.now() >= otp.expires_at:
            otp.is_used = True
            otp.save(update_fields=["is_used"])

            return False, str(
                _("Ce code de vérification a expiré."),
            )

        if otp.attempts >= cls.MAX_ATTEMPTS:
            otp.is_used = True
            otp.save(update_fields=["is_used"])

            return False, str(
                _("Nombre maximal de tentatives atteint."),
            )

        if not secrets.compare_digest(
            otp.code,
            str(code).strip(),
        ):
            otp.attempts += 1

            if otp.attempts >= cls.MAX_ATTEMPTS:
                otp.is_used = True

            otp.save(update_fields=["attempts", "is_used"])

            return False, str(
                _("Code de vérification incorrect."),
            )

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        return True, str(
            _("Adresse e-mail vérifiée avec succès."),
        )

    @classmethod
    def resend_otp(
        cls,
        user,
        otp_type: str,
    ) -> OTPVerification:
        """Invalidate the previous OTP and send a new one."""
        return cls.send_otp(
            user=user,
            otp_type=otp_type,
        )
