"""Tests du parcours d'accès aux espaces de travail."""

from http import HTTPStatus

import pytest
from django.urls import reverse

from stagelink.profiles.models import CompanyProfile
from stagelink.profiles.models import StudentProfile
from stagelink.users.tests.factories import UserFactory
from stagelink.utils.enums import Role

pytestmark = pytest.mark.django_db

STUDENT_DASHBOARD = reverse("core:student-dashboard")
COMPANY_DASHBOARD = reverse("core:company-dashboard")


def make_user(role=Role.STUDENT, *, verified=True, with_profile=True):
    user = UserFactory.create(role=role, email_verified=verified)
    if with_profile and role == Role.STUDENT:
        StudentProfile.objects.create(user=user, field_of_study="Droit", level="L2")
    if with_profile and role == Role.COMPANY:
        CompanyProfile.objects.create(user=user, company_name="ACME", address="Douala")
    return user


class TestWorkspaceAccess:
    @pytest.mark.parametrize("url", [STUDENT_DASHBOARD, COMPANY_DASHBOARD])
    def test_anonymous_redirected_to_login(self, client, url):
        response = client.get(url)
        assert response.status_code == HTTPStatus.FOUND
        assert response.url.startswith(reverse("users:login"))

    def test_unverified_email_redirected_to_verification(self, client):
        client.force_login(make_user(verified=False, with_profile=False))
        response = client.get(STUDENT_DASHBOARD)
        assert response.url == reverse("users:verify-email")

    def test_missing_profile_redirected_to_completion(self, client):
        client.force_login(make_user(Role.COMPANY, with_profile=False))
        response = client.get(COMPANY_DASHBOARD)
        assert response.url == reverse("profiles:company-complete")

    def test_student_cannot_access_company_space(self, client):
        client.force_login(make_user(Role.STUDENT))
        assert client.get(COMPANY_DASHBOARD).status_code == HTTPStatus.FORBIDDEN
        assert (
            client.get(reverse("profiles:company-detail")).status_code
            == HTTPStatus.FORBIDDEN
        )

    def test_company_cannot_access_student_space(self, client):
        client.force_login(make_user(Role.COMPANY))
        assert client.get(STUDENT_DASHBOARD).status_code == HTTPStatus.FORBIDDEN
        assert (
            client.get(reverse("profiles:student-edit")).status_code
            == HTTPStatus.FORBIDDEN
        )

    @pytest.mark.parametrize(
        ("role", "url"),
        [(Role.STUDENT, STUDENT_DASHBOARD), (Role.COMPANY, COMPANY_DASHBOARD)],
    )
    def test_complete_user_reaches_dashboard(self, client, role, url):
        client.force_login(make_user(role))
        assert client.get(reverse("users:redirect")).url == url
        assert client.get(url).status_code == HTTPStatus.OK

    def test_completion_page_unavailable_once_profile_exists(self, client):
        client.force_login(make_user(Role.STUDENT))
        response = client.get(reverse("profiles:student-complete"))
        assert response.url == reverse("users:redirect")

    @pytest.mark.parametrize(
        "name",
        ["student-detail", "student-edit"],
    )
    def test_student_profile_pages_render(self, client, name):
        client.force_login(make_user(Role.STUDENT))
        assert client.get(reverse(f"profiles:{name}")).status_code == HTTPStatus.OK

    @pytest.mark.parametrize(
        "name",
        ["company-detail", "company-edit"],
    )
    def test_company_profile_pages_render(self, client, name):
        client.force_login(make_user(Role.COMPANY))
        assert client.get(reverse(f"profiles:{name}")).status_code == HTTPStatus.OK


class TestOnboardingFlow:
    def test_signup_verify_complete_dashboard(self, client, monkeypatch):
        sent_codes = []
        monkeypatch.setattr(
            "stagelink.users.services.otp.send_otp_email.delay",
            lambda verification_id, code: sent_codes.append(code),
        )

        response = client.post(
            reverse("users:signup"),
            {
                "role": Role.STUDENT,
                "email": "etudiante@example.com",
                "password": "Stage-Link-2026!",
                "password_confirmation": "Stage-Link-2026!",
            },
        )
        assert response.url == reverse("users:verify-email")
        assert len(sent_codes) == 1

        response = client.post(reverse("users:verify-email"), {"code": "000000"})
        assert response.status_code == HTTPStatus.OK  # code incorrect : formulaire réaffiché

        response = client.post(reverse("users:verify-email"), {"code": sent_codes[0]})
        assert response.url == reverse("users:redirect")
        assert client.get(response.url).url == reverse("profiles:student-complete")

        response = client.post(
            reverse("profiles:student-complete"),
            {
                "name": "Adora N.",
                "field_of_study": "Génie logiciel",
                "level": "BTS 2",
                "skills": "Python, Django, python",
                "language": "fr",
            },
        )
        assert response.url == STUDENT_DASHBOARD

        profile = StudentProfile.objects.get(user__email="etudiante@example.com")
        assert profile.skills == ["Python", "Django"]
        assert profile.user.name == "Adora N."
        assert client.get(STUDENT_DASHBOARD).status_code == HTTPStatus.OK

    def test_resend_code_is_rate_limited(self, client, monkeypatch):
        sent_codes = []
        monkeypatch.setattr(
            "stagelink.users.services.otp.send_otp_email.delay",
            lambda verification_id, code: sent_codes.append(code),
        )
        client.force_login(make_user(verified=False, with_profile=False))

        client.post(reverse("users:verify-email"), {"resend": "1"})
        client.post(reverse("users:verify-email"), {"resend": "1"})

        assert len(sent_codes) == 1

    def test_company_phone_number_is_normalized(self, client):
        user = make_user(Role.COMPANY, with_profile=False)
        client.force_login(user)

        response = client.post(
            reverse("profiles:company-complete"),
            {
                "company_name": "ACME",
                "address": "Douala",
                "phone_number": "+237 6 77 12 34 56",
            },
        )
        assert response.url == COMPANY_DASHBOARD
        assert user.company_profile.phone_number == "+237677123456"
