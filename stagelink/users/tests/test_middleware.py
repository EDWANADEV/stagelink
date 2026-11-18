from __future__ import annotations

from http import HTTPStatus
from unittest.mock import patch

import pytest
from django.urls import reverse

from stagelink.profiles.models import CompanyProfile
from stagelink.profiles.models import StudentProfile
from stagelink.users.middleware import PENDING_SIGNUP_TOKEN_SESSION_KEY
from stagelink.users.otp_utils import create_otp_token
from stagelink.users.services import OtpRateLimitError
from stagelink.users.tests.factories import UserFactory
from stagelink.utils.enums import OTPType
from stagelink.utils.enums import Role

pytestmark = pytest.mark.django_db

# Page protégée quelconque, interceptée par le middleware.
PROTECTED_URL = "/about/"


@pytest.fixture
def verified_student():
    """Étudiant dont l'adresse e-mail est vérifiée."""
    return UserFactory(role=Role.STUDENT, email_verified=True)


class TestProfileCompletionMiddleware:
    """Tests du middleware de complétion du profil."""

    def test_anonymous_user_is_not_redirected(self, client):
        response = client.get(PROTECTED_URL)

        assert response.status_code == HTTPStatus.OK

    def test_staff_user_is_not_redirected(self, client):
        client.force_login(UserFactory(is_staff=True))

        response = client.get(PROTECTED_URL)

        assert response.status_code == HTTPStatus.OK

    def test_unverified_user_reuses_pending_session_token(self, client):
        user = UserFactory(role=Role.STUDENT)
        token = create_otp_token("otp-id", str(user.pk), OTPType.SIGNUP)
        client.force_login(user)
        session = client.session
        session[PENDING_SIGNUP_TOKEN_SESSION_KEY] = token
        session.save()

        response = client.get(PROTECTED_URL)

        assert response.url == reverse(
            "users:verify_otp",
            kwargs={"purpose": OTPType.SIGNUP, "token": token},
        )

    def test_unverified_user_receives_new_otp(self, client, mailoutbox):
        user = UserFactory(role=Role.STUDENT)
        client.force_login(user)

        response = client.get(PROTECTED_URL)

        token = client.session[PENDING_SIGNUP_TOKEN_SESSION_KEY]
        assert response.url == reverse(
            "users:verify_otp",
            kwargs={"purpose": OTPType.SIGNUP, "token": token},
        )
        assert len(mailoutbox) == 1

    def test_unverified_user_is_logged_out_when_rate_limited(self, client):
        client.force_login(UserFactory(role=Role.STUDENT))

        with patch(
            "stagelink.users.middleware.OtpService.create",
            side_effect=OtpRateLimitError,
        ):
            response = client.get(PROTECTED_URL)

        assert response.url == reverse("users:signin")
        assert "_auth_user_id" not in client.session

    def test_student_without_profile_is_redirected(
        self,
        client,
        verified_student,
    ):
        client.force_login(verified_student)

        response = client.get(PROTECTED_URL)

        assert response.url == reverse("profiles:complete")

    def test_company_without_profile_is_redirected(self, client):
        client.force_login(
            UserFactory(role=Role.COMPANY, email_verified=True),
        )

        response = client.get(PROTECTED_URL)

        assert response.url == reverse("profiles:complete")

    def test_soft_deleted_profile_counts_as_missing(
        self,
        client,
        verified_student,
    ):
        profile = StudentProfile.objects.create(
            user=verified_student,
            field_of_study="Informatique",
            level="Licence",
        )
        profile.soft_delete()
        client.force_login(verified_student)

        response = client.get(PROTECTED_URL)

        assert response.url == reverse("profiles:complete")

    def test_completed_profile_is_not_redirected(self, client):
        user = UserFactory(role=Role.COMPANY, email_verified=True)
        CompanyProfile.objects.create(
            user=user,
            company_name="HooYia",
            address="Douala",
        )
        client.force_login(user)

        response = client.get(PROTECTED_URL)

        assert response.status_code == HTTPStatus.OK

    @pytest.mark.parametrize(
        "path",
        [
            "/static/css/output.css",
            "/media/cv/file.pdf",
        ],
    )
    def test_static_and_media_paths_are_exempt(
        self,
        client,
        verified_student,
        path,
    ):
        client.force_login(verified_student)

        response = client.get(path)

        assert response.status_code != HTTPStatus.FOUND

    def test_logout_is_exempt(self, client, verified_student):
        client.force_login(verified_student)

        response = client.post(reverse("users:logout"))

        assert response.url == reverse("users:signin")
