from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from stagelink.utils.email import EmailUtil


@shared_task(ignore_result=True)
def send_otp_email(
    verification_id: str,
    code: str,
) -> None:
    """Envoie le code OTP par e-mail."""
    verification = (
        OTPVerification.objects
        .select_related("user")
        .get(id=verification_id)
    )

    templates = {
        "SIGNUP": (
            "emails/otp/signup.html",
            _("Votre code de vérification StageLink"),
        ),
        "PASSWORD_RESET": (
            "emails/otp/password_reset.html",
            _("Votre code de réinitialisation StageLink"),
        ),
    }
    try:
        template_name, subject = templates[verification.otp_type]
    except KeyError as exc:
        msg = f"Type OTP non pris en charge : {verification.otp_type}"
        raise ValueError(msg) from exc

    context = {
        "code": code,
        "otp_code": code,
        "expiration_minutes": settings.OTP_EXPIRATION_MINUTES,
        "user": verification.user,
    }

    html_message = render_to_string(template_name, context)

    text_message = _(
        "Votre code de vérification StageLink est : %(code)s\n\n"
        "Ce code expire dans %(minutes)s minutes.",
    ) % {
        "code": code,
        "minutes": settings.OTP_EXPIRATION_MINUTES,
    }

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[verification.user.email],
    )

        context = {
            "full_name": full_name,
            "code": code,
            "validity": validity,
        }

    email.send(fail_silently=False)
