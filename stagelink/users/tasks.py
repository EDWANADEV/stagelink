from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from .models import OTPVerification


@shared_task
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

    context = {
        "code": code,
        "expiration_minutes": settings.OTP_EXPIRATION_MINUTES,
        "user": verification.user,
    }

    html_message = render_to_string(
        "emails/otp/verification.html",
        context,
    )

    text_message = _(
        "Votre code de vérification StageLink est : %(code)s\n\n"
        "Ce code expire dans %(minutes)s minutes."
    ) % {
        "code": code,
        "minutes": settings.OTP_EXPIRATION_MINUTES,
    }

    email = EmailMultiAlternatives(
        subject=_("Votre code de vérification StageLink"),
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[verification.user.email],
    )

    email.attach_alternative(
        html_message,
        "text/html",
    )

    email.send(fail_silently=False)