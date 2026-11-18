from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from stagelink.users.models import OTPVerification
from stagelink.users.tasks import send_otp_email
from stagelink.users.tests.factories import UserFactory
from stagelink.utils.enums import OTPType

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("otp_type", "subject"),
    [
        (OTPType.SIGNUP, "vérification"),
        (OTPType.PASSWORD_RESET, "réinitialisation"),
    ],
)
def test_send_otp_email_uses_type_template_and_configured_expiration(
    settings,
    otp_type,
    subject,
):
    settings.OTP_EXPIRATION_MINUTES = 7
    user = UserFactory(name="StageLink User")
    verification = OTPVerification.objects.create(
        user=user,
        code="hashed-code",
        otp_type=otp_type,
        expires_at=timezone.now() + timedelta(minutes=7),
    )

    send_otp_email(str(verification.pk), "012345")

    assert len(mail.outbox) == 1
    sent_email = mail.outbox[0]
    assert sent_email.to == [user.email]
    assert subject in sent_email.subject.lower()
    assert "012345" in sent_email.body
    assert "012345" in sent_email.alternatives[0][0]
    assert "7 minutes" in sent_email.alternatives[0][0]
