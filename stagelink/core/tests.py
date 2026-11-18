from datetime import timedelta

import pytest
from django.utils import timezone

from stagelink.users.models import OTPVerification
from stagelink.users.tests.factories import UserFactory
from stagelink.utils.enums import OTPType

pytestmark = pytest.mark.django_db


def create_verification():
    user = UserFactory()
    return OTPVerification.objects.create(
        user=user,
        code="hashed-code",
        otp_type=OTPType.SIGNUP,
        expires_at=timezone.now() + timedelta(minutes=5),
    )


def test_soft_delete_hides_instance_from_default_manager():
    verification = create_verification()

    verification.soft_delete(verification.user)

    assert not OTPVerification.objects.filter(pk=verification.pk).exists()
    restored = OTPVerification.all_objects.get(pk=verification.pk)
    assert restored.updated_by_id == verification.user_id


def test_restore_returns_instance_to_default_manager():
    verification = create_verification()
    verification.soft_delete(verification.user)

    verification.restore(verification.user)

    assert OTPVerification.objects.get(pk=verification.pk).is_deleted is False
