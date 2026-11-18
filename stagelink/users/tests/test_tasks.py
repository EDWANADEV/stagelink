import pytest
from django.core import mail

from stagelink.users.tasks import send_otp_email_task
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
    otp_type,
    subject,
):
    send_otp_email_task(
        email="stage-link@example.com",
        full_name="StageLink User",
        code="012345",
        validity=7,
        otp_type=otp_type,
        language="fr",
    )

    assert len(mail.outbox) == 1
    sent_email = mail.outbox[0]
    assert sent_email.bcc == ["stage-link@example.com"]
    assert subject in sent_email.subject.lower()
    assert "012345" in sent_email.body
    assert "StageLink User" in sent_email.body
    assert "7 minutes" in sent_email.body
