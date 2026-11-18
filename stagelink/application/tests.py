from datetime import timedelta
from http import HTTPStatus

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from stagelink.application.models import Application
from stagelink.application.models import ApplicationStatusHistory
from stagelink.application.services import ApplicationService
from stagelink.notifications.models import Notification
from stagelink.offers.models import InternshipOffer
from stagelink.profiles.models import CompanyProfile
from stagelink.profiles.models import StudentProfile
from stagelink.users.tests.factories import UserFactory
from stagelink.utils.enums import ApplicationMode
from stagelink.utils.enums import ApplicationStatus
from stagelink.utils.enums import OfferStatus
from stagelink.utils.enums import Role

pytestmark = pytest.mark.django_db


@pytest.fixture
def student_profile():
    user = UserFactory(role=Role.STUDENT, email_verified=True)
    return StudentProfile.objects.create(
        user=user,
        field_of_study="Informatique",
        level="Licence",
    )


@pytest.fixture
def internal_offer():
    user = UserFactory(role=Role.COMPANY, email_verified=True)
    company = CompanyProfile.objects.create(
        user=user,
        company_name="StageLink",
        address="Douala",
    )
    return InternshipOffer.objects.create(
        company=company,
        created_by=user,
        title="Développeur stagiaire",
        description="Développement web.",
        domain="Informatique",
        location="Douala",
        duration_days=90,
        application_deadline=timezone.now() + timedelta(days=30),
        status=OfferStatus.PUBLISHED,
        published_at=timezone.now(),
        application_mode=ApplicationMode.INTERNAL,
    )


def test_submit_creates_internal_application(student_profile, internal_offer):
    with TestCase.captureOnCommitCallbacks(execute=True):
        application = ApplicationService.submit(
            student=student_profile,
            offer=internal_offer,
            cover_letter="Ma motivation.",
        )

    assert application.status == ApplicationStatus.RECEIVED
    assert application.cover_letter == "Ma motivation."
    assert Application.objects.filter(pk=application.pk).exists()
    assert ApplicationStatusHistory.objects.filter(
        application=application,
        new_status=ApplicationStatus.RECEIVED,
    ).exists()
    assert Notification.objects.filter(user=internal_offer.company.user).exists()


def test_company_can_advance_application_and_student_is_notified(
    student_profile,
    internal_offer,
):
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.RECEIVED,
        created_by=student_profile.user,
    )

    with TestCase.captureOnCommitCallbacks(execute=True):
        updated = ApplicationService.change_status(
            application=application,
            new_status=ApplicationStatus.VIEWED,
            updated_by=internal_offer.company.user,
        )

    assert updated.status == ApplicationStatus.VIEWED
    assert ApplicationStatusHistory.objects.filter(
        application=application,
        previous_status=ApplicationStatus.RECEIVED,
        new_status=ApplicationStatus.VIEWED,
        changed_by=internal_offer.company.user,
    ).exists()
    assert Notification.objects.filter(user=student_profile.user).exists()


def test_interview_status_requires_a_scheduled_time(
    student_profile,
    internal_offer,
):
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.VIEWED,
        created_by=student_profile.user,
    )

    with pytest.raises(ValidationError, match="date et l'heure"):
        ApplicationService.change_status(
            application=application,
            new_status=ApplicationStatus.INTERVIEW,
            updated_by=internal_offer.company.user,
        )


def test_company_schedules_interview_and_student_is_notified(
    student_profile,
    internal_offer,
):
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.VIEWED,
        created_by=student_profile.user,
    )
    interview_at = timezone.now() + timedelta(days=3)

    with TestCase.captureOnCommitCallbacks(execute=True):
        updated = ApplicationService.change_status(
            application=application,
            new_status=ApplicationStatus.INTERVIEW,
            updated_by=internal_offer.company.user,
            interview_at=interview_at,
        )

    assert updated.interview_at == interview_at
    assert ApplicationStatusHistory.objects.filter(
        application=application,
        previous_status=ApplicationStatus.VIEWED,
        new_status=ApplicationStatus.INTERVIEW,
    ).exists()
    assert Notification.objects.filter(user=student_profile.user).exists()


def test_acceptance_cannot_exceed_offer_positions(
    student_profile,
    internal_offer,
):
    internal_offer.available_positions = 1
    internal_offer.save(update_fields=["available_positions"])
    another_student = StudentProfile.objects.create(
        user=UserFactory(role=Role.STUDENT, email_verified=True),
        field_of_study="Marketing",
        level="Licence",
    )
    applications = [
        Application.objects.create(
            student=profile,
            offer=internal_offer,
            status=ApplicationStatus.INTERVIEW,
            interview_at=timezone.now() + timedelta(days=3),
            created_by=profile.user,
        )
        for profile in (student_profile, another_student)
    ]

    ApplicationService.change_status(
        application=applications[0],
        new_status=ApplicationStatus.ACCEPTED,
        updated_by=internal_offer.company.user,
    )

    with pytest.raises(ValidationError, match="places"):
        ApplicationService.change_status(
            application=applications[1],
            new_status=ApplicationStatus.ACCEPTED,
            updated_by=internal_offer.company.user,
        )

    applications[1].refresh_from_db()
    internal_offer.refresh_from_db()
    assert applications[1].status == ApplicationStatus.INTERVIEW
    assert internal_offer.available_positions == 1


def test_student_can_withdraw_from_interview_at_exact_24_hour_boundary(
    student_profile,
    internal_offer,
    monkeypatch,
):
    now = timezone.now()
    monkeypatch.setattr("stagelink.application.services.timezone.now", lambda: now)
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.INTERVIEW,
        interview_at=now + timedelta(hours=24),
        created_by=student_profile.user,
    )

    with TestCase.captureOnCommitCallbacks(execute=True):
        updated = ApplicationService.withdraw(
            application=application,
            student=student_profile,
            reason="J'ai accepté une autre proposition.",
        )

    assert updated.status == ApplicationStatus.WITHDRAWN
    event = ApplicationStatusHistory.objects.get(application=application)
    assert event.previous_status == ApplicationStatus.INTERVIEW
    assert event.new_status == ApplicationStatus.WITHDRAWN
    assert event.reason == "J'ai accepté une autre proposition."
    assert Notification.objects.filter(user=internal_offer.company.user).exists()


@pytest.mark.parametrize(
    ("interview_offset", "reason"),
    [
        (timedelta(days=2), "   "),
        (timedelta(hours=23), "Motif fourni."),
        (timedelta(hours=0), "Motif fourni."),
    ],
)
def test_interview_withdrawal_requires_reason_and_24_hours(
    student_profile,
    internal_offer,
    interview_offset,
    reason,
):
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.INTERVIEW,
        interview_at=timezone.now() + interview_offset,
        created_by=student_profile.user,
    )

    with pytest.raises(ValidationError):
        ApplicationService.withdraw(
            application=application,
            student=student_profile,
            reason=reason,
        )

    application.refresh_from_db()
    assert application.status == ApplicationStatus.INTERVIEW
    assert not ApplicationStatusHistory.objects.filter(
        application=application,
    ).exists()


def test_submit_rejects_duplicate_even_if_soft_deleted(
    student_profile,
    internal_offer,
):
    existing = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        created_by=student_profile.user,
    )
    existing.soft_delete(student_profile.user)

    with pytest.raises(ValidationError, match="déjà candidaté"):
        ApplicationService.submit(
            student=student_profile,
            offer=internal_offer,
        )

    assert (
        Application.all_objects.filter(
            student=student_profile,
            offer=internal_offer,
        ).count()
        == 1
    )


def test_submit_rejects_external_offer(student_profile, internal_offer):
    internal_offer.application_mode = ApplicationMode.EXTERNAL
    internal_offer.application_url = "https://example.com/apply"
    internal_offer.save(update_fields=["application_mode", "application_url"])

    with pytest.raises(ValidationError, match="externe"):
        ApplicationService.submit(student=student_profile, offer=internal_offer)


def test_student_can_submit_through_offer_flow(
    client,
    student_profile,
    internal_offer,
):
    client.force_login(student_profile.user)

    response = client.post(
        reverse("application:submit", kwargs={"offer_pk": internal_offer.pk}),
        {"cover_letter": "Ma motivation."},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == reverse("application:student-list")
    assert Application.objects.filter(
        student=student_profile,
        offer=internal_offer,
        cover_letter="Ma motivation.",
    ).exists()


def test_student_application_list_is_scoped_to_current_student(
    client,
    student_profile,
    internal_offer,
):
    other_student = StudentProfile.objects.create(
        user=UserFactory(role=Role.STUDENT, email_verified=True),
        field_of_study="Marketing",
        level="Licence",
    )
    own_application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        created_by=student_profile.user,
    )
    Application.objects.create(
        student=other_student,
        offer=internal_offer,
        created_by=other_student.user,
    )
    client.force_login(student_profile.user)

    response = client.get(reverse("application:student-list"))

    assert response.status_code == HTTPStatus.OK
    assert list(response.context["applications"]) == [own_application]
    assert response.context["applications"][0].offer.title in response.content.decode()


def test_company_application_list_is_scoped_to_its_own_offers(
    client,
    student_profile,
    internal_offer,
):
    other_company_user = UserFactory(role=Role.COMPANY, email_verified=True)
    another_offer = internal_offer.__class__.objects.create(
        company=CompanyProfile.objects.create(
            user=other_company_user,
            company_name="Autre entreprise",
            address="Yaoundé",
        ),
        created_by=other_company_user,
        title="Autre stage",
        description="Une autre offre.",
        domain="Marketing",
        location="Yaoundé",
        duration_days=60,
        application_deadline=timezone.now() + timedelta(days=15),
        status=OfferStatus.PUBLISHED,
        published_at=timezone.now(),
        application_mode=ApplicationMode.INTERNAL,
    )
    own = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        created_by=student_profile.user,
    )
    Application.objects.create(
        student=student_profile,
        offer=another_offer,
        created_by=student_profile.user,
    )
    client.force_login(internal_offer.company.user)

    response = client.get(reverse("application:company-list"))

    assert response.status_code == HTTPStatus.OK
    assert list(response.context["applications"]) == [own]
    assert student_profile.user.email.encode() not in response.content


def test_company_can_change_status_through_its_application_route(
    client,
    student_profile,
    internal_offer,
):
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.RECEIVED,
        created_by=student_profile.user,
    )
    client.force_login(internal_offer.company.user)

    response = client.post(
        reverse("application:change-status", kwargs={"pk": application.pk}),
        {"status": ApplicationStatus.VIEWED},
    )

    application.refresh_from_db()
    assert response.status_code == HTTPStatus.FOUND
    assert application.status == ApplicationStatus.VIEWED
    assert ApplicationStatusHistory.objects.filter(
        application=application,
        new_status=ApplicationStatus.VIEWED,
    ).exists()


def test_company_cannot_change_status_for_another_company(
    client,
    student_profile,
    internal_offer,
):
    other_company_user = UserFactory(role=Role.COMPANY, email_verified=True)
    other_company = CompanyProfile.objects.create(
        user=other_company_user,
        company_name="Autre entreprise",
        address="Yaoundé",
    )
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer.__class__.objects.create(
            company=other_company,
            created_by=other_company_user,
            title="Autre stage",
            description="Une autre offre.",
            domain="Marketing",
            location="Yaoundé",
            duration_days=60,
            application_deadline=timezone.now() + timedelta(days=15),
            status=OfferStatus.PUBLISHED,
            published_at=timezone.now(),
            application_mode=ApplicationMode.INTERNAL,
        ),
        status=ApplicationStatus.RECEIVED,
        created_by=student_profile.user,
    )
    client.force_login(internal_offer.company.user)

    response = client.post(
        reverse("application:change-status", kwargs={"pk": application.pk}),
        {"status": ApplicationStatus.VIEWED},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    application.refresh_from_db()
    assert application.status == ApplicationStatus.RECEIVED


def test_student_can_withdraw_own_application_before_interview(
    client,
    student_profile,
    internal_offer,
):
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.RECEIVED,
        created_by=student_profile.user,
    )
    client.force_login(student_profile.user)

    response = client.post(
        reverse("application:withdraw", kwargs={"pk": application.pk}),
    )

    application.refresh_from_db()
    assert response.status_code == HTTPStatus.FOUND
    assert application.status == ApplicationStatus.WITHDRAWN


def test_student_cannot_withdraw_another_students_application(
    client,
    student_profile,
    internal_offer,
):
    other_student = UserFactory(role=Role.STUDENT, email_verified=True)
    StudentProfile.objects.create(
        user=other_student,
        field_of_study="Droit",
        level="Licence",
    )
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.RECEIVED,
        created_by=student_profile.user,
    )
    client.force_login(other_student)

    response = client.post(
        reverse("application:withdraw", kwargs={"pk": application.pk}),
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    application.refresh_from_db()
    assert application.status == ApplicationStatus.RECEIVED
