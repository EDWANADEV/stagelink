from datetime import timedelta
from http import HTTPStatus

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from stagelink.application.models import Application
from stagelink.offers.models import InternshipOffer
from stagelink.profiles.models import CompanyProfile
from stagelink.profiles.models import StudentProfile
from stagelink.profiles.services import has_completed_profile
from stagelink.users.tests.factories import UserFactory
from stagelink.utils.enums import Role

pytestmark = pytest.mark.django_db


def test_student_profile_requires_name_field_of_study_and_level():
    user = UserFactory(role=Role.STUDENT, name="")
    profile = StudentProfile.objects.create(
        user=user,
        field_of_study="Informatique",
        level="Licence",
    )

    assert not has_completed_profile(user)

    user.name = "Étudiante StageLink"
    user.save(update_fields=["name"])

    assert has_completed_profile(user)
    assert profile.skills == []
    assert not profile.cv


def test_whitespace_only_required_profile_fields_are_incomplete():
    user = UserFactory(role=Role.COMPANY, email_verified=True)
    CompanyProfile.objects.create(
        user=user,
        company_name="   ",
        address="Douala",
    )

    assert not has_completed_profile(user)


def test_student_language_must_match_existing_model_choices():
    user = UserFactory(role=Role.STUDENT)
    profile = StudentProfile.objects.create(
        user=user,
        field_of_study="Informatique",
        level="Licence",
        language="",
    )

    assert not has_completed_profile(user)

    profile.language = "fr"
    profile.save(update_fields=["language"])

    assert has_completed_profile(user)


def test_company_profile_does_not_require_optional_fields():
    user = UserFactory(role=Role.COMPANY, email_verified=True)
    CompanyProfile.objects.create(
        user=user,
        company_name="StageLink SARL",
        address="Douala",
    )

    assert has_completed_profile(user)


def test_student_cv_download_is_private_and_attachment(client):
    user = UserFactory(role=Role.STUDENT, email_verified=True)
    profile = StudentProfile.objects.create(
        user=user,
        field_of_study="Informatique",
        level="Licence",
    )
    profile.cv.save("resume.pdf", ContentFile(b"%PDF-1.4\nCV"), save=True)
    client.force_login(user)

    response = client.get(
        reverse("profiles:student-cv", kwargs={"profile_pk": profile.pk}),
    )

    assert response.status_code == HTTPStatus.OK
    assert response["Content-Disposition"].startswith("attachment;")
    assert response["Cache-Control"] == "private, no-store"
    assert b"".join(response.streaming_content) == b"%PDF-1.4\nCV"


def test_another_student_cannot_download_cv(client):
    owner = UserFactory(role=Role.STUDENT, email_verified=True)
    profile = StudentProfile.objects.create(
        user=owner,
        field_of_study="Informatique",
        level="Licence",
    )
    profile.cv.save("resume.pdf", ContentFile(b"%PDF-1.4\nCV"), save=True)
    other_student = UserFactory(
        role=Role.STUDENT,
        email_verified=True,
        name="Autre étudiant",
    )
    StudentProfile.objects.create(
        user=other_student,
        field_of_study="Marketing",
        level="Licence",
    )
    client.force_login(other_student)

    response = client.get(
        reverse("profiles:student-cv", kwargs={"profile_pk": profile.pk}),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_company_with_application_can_download_student_cv(client):
    student_user = UserFactory(role=Role.STUDENT, email_verified=True)
    student = StudentProfile.objects.create(
        user=student_user,
        field_of_study="Informatique",
        level="Licence",
    )
    student.cv.save("resume.pdf", ContentFile(b"%PDF-1.4\nCV"), save=True)
    company_user = UserFactory(role=Role.COMPANY, email_verified=True)
    company = CompanyProfile.objects.create(
        user=company_user,
        company_name="StageLink",
        address="Douala",
    )
    offer = InternshipOffer.objects.create(
        company=company,
        title="Stage développeur",
        description="Stage de développement.",
        domain="Informatique",
        location="Douala",
        duration_days=90,
        application_deadline=timezone.now() + timedelta(days=30),
    )
    Application.objects.create(student=student, offer=offer)
    client.force_login(company_user)

    response = client.get(
        reverse("profiles:student-cv", kwargs={"profile_pk": student.pk}),
    )

    assert response.status_code == HTTPStatus.OK
    assert response["Content-Disposition"].startswith("attachment;")


def test_unrelated_company_cannot_download_student_cv(client):
    student_user = UserFactory(role=Role.STUDENT, email_verified=True)
    student = StudentProfile.objects.create(
        user=student_user,
        field_of_study="Informatique",
        level="Licence",
    )
    student.cv.save("resume.pdf", ContentFile(b"%PDF-1.4\nCV"), save=True)
    company_user = UserFactory(role=Role.COMPANY, email_verified=True)
    CompanyProfile.objects.create(
        user=company_user,
        company_name="Entreprise sans candidature",
        address="Douala",
    )
    client.force_login(company_user)

    response = client.get(
        reverse("profiles:student-cv", kwargs={"profile_pk": student.pk}),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_public_cv_media_path_is_not_served(client):
    response = client.get("/media/cv/resume.pdf")

    assert response.status_code == HTTPStatus.NOT_FOUND
