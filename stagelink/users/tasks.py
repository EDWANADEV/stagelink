from __future__ import annotations

from celery import shared_task
from django.utils.translation import gettext_lazy as _

from stagelink.utils.email import EmailUtil
from stagelink.utils.enums import OTPType

OTP_EMAILS = {
    OTPType.SIGNUP: (
        "emails/otp/signup.html",
        _("Votre code de vérification StageLink"),
    ),
    OTPType.PASSWORD_RESET: (
        "emails/otp/password_reset.html",
        _("Votre code de réinitialisation StageLink"),
    ),
}


@shared_task(ignore_result=True)
def send_otp_email_task(  # noqa: PLR0913
    *,
    email: str,
    full_name: str,
    code: str,
    validity: int,
    otp_type: str,
    language: str,
) -> None:
    """Envoie un OTP par e-mail à l'aide du service commun de courriel."""
    try:
        template, subject = OTP_EMAILS[otp_type]
    except KeyError as exc:
        msg = f"Type OTP non pris en charge : {otp_type}"
        raise ValueError(msg) from exc

    EmailUtil.send_email_with_template(
        template=template,
        context={
            "full_name": full_name,
            "otp_code": code,
            "validity": validity,
        },
        receivers=[email],
        subject=subject,
        language=language,
    )
