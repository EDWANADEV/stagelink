from __future__ import annotations

from celery import shared_task
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from stagelink.utils.email import EmailUtil


@shared_task
def send_otp_email_task(
    email: str,
    full_name: str,
    code: str,
    validity: int,
    otp_type: str,
    language: str | None = None,
) -> bool:
    """
    Envoie le code OTP de manière asynchrone avec Celery.
    """

    lang = language or settings.LANGUAGE_CODE

    template_by_type = {
        "SIGNUP": "emails/otp/signup.html",
        "PASSWORD_RESET": "emails/otp/password_reset.html",
    }

    template = template_by_type.get(otp_type)

    if not template:
        return False

    with translation.override(lang):
        subject = _("Votre code de vérification StageLink")

        context = {
            "full_name": full_name,
            "code": code,
            "validity": validity,
        }

        return EmailUtil.send_email_with_template(
            template=template,
            context=context,
            receivers=[email],
            subject=subject,
            language=lang,
        )