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
    language: str | None = None,
) -> bool:
    """
    Envoie le code OTP de manière asynchrone avec Celery.
    """

    lang = language or settings.LANGUAGE_CODE

    with translation.override(lang):
        subject = _("Votre code de vérification StageLink")

        context = {
            "full_name": full_name,
            "code": code,
            "validity": validity,
        }

        return EmailUtil.send_email_with_template(
            template="emails/otp.html",
            context=context,
            receivers=[email],
            subject=subject,
            language=lang,
        )