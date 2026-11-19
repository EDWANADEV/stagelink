from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from http import HTTPStatus
from threading import Barrier
from types import SimpleNamespace

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from stagelink.application.admin import ApplicationAdmin
from stagelink.application.admin import ApplicationStatusHistoryAdmin
from stagelink.application.models import Application
from stagelink.application.models import ApplicationStatusHistory
from stagelink.application.services import ApplicationService
from stagelink.application.views import CompanyApplicationsView
from stagelink.application.views import StudentApplicationsView
from stagelink.notifications.models import Notification
from stagelink.offers.models import InternshipOffer
from stagelink.offers.services import update_offer
from stagelink.profiles.models import CompanyProfile
from stagelink.profiles.models import StudentProfile
from stagelink.users.tests.factories import UserFactory
from stagelink.utils.enums import ApplicationMode
from stagelink.utils.enums import ApplicationStatus
from stagelink.utils.enums import OfferStatus
from stagelink.utils.enums import Role

pytestmark = pytest.mark.django_db
EXPECTED_APPLICATION_LIST_SIZE = 3
EXPECTED_APPLICATION_LIST_QUERY_COUNT = 3


def test_application_admin_preserves_relations_and_disables_hard_delete():
    model_admin = ApplicationAdmin(Application, AdminSite())
    history_admin = ApplicationStatusHistoryAdmin(
        ApplicationStatusHistory,
        AdminSite(),
    )

    assert {"student", "offer"}.issubset(model_admin.readonly_fields)
    assert model_admin.has_delete_permission(None) is False
    assert history_admin.has_add_permission(None) is False
    assert history_admin.has_change_permission(None) is False
    assert history_admin.has_delete_permission(None) is False


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


def add_profile_cv(student_profile):
    student_profile.cv = "cv/resume.pdf"
    student_profile.save(update_fields=["cv"])


def test_submit_creates_internal_application(student_profile, internal_offer):
    add_profile_cv(student_profile)
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
    assert Notification.objects.filter(
        user=internal_offer.company.user,
    ).count() == 1


def test_notification_failure_rolls_back_submission(
    student_profile,
    internal_offer,
    monkeypatch,
):
    add_profile_cv(student_profile)

    def fail_create(**kwargs):
        raise RuntimeError

    monkeypatch.setattr(Notification.objects, "create", fail_create)

    with pytest.raises(RuntimeError):
        ApplicationService.submit(
            student=student_profile,
            offer=internal_offer,
        )

    assert Application.all_objects.filter(
        student=student_profile,
        offer=internal_offer,
    ).count() == 0
    assert ApplicationStatusHistory.objects.count() == 0


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
    assert Notification.objects.filter(user=student_profile.user).count() == 1
    with pytest.raises(ValidationError):
        ApplicationService.change_status(
            application=updated,
            new_status=ApplicationStatus.VIEWED,
            updated_by=internal_offer.company.user,
        )
    assert Notification.objects.filter(user=student_profile.user).count() == 1


@pytest.mark.parametrize(
    ("previous_status", "new_status"),
    [
        (ApplicationStatus.RECEIVED, ApplicationStatus.VIEWED),
        (ApplicationStatus.RECEIVED, ApplicationStatus.REJECTED),
        (ApplicationStatus.VIEWED, ApplicationStatus.INTERVIEW),
        (ApplicationStatus.VIEWED, ApplicationStatus.REJECTED),
        (ApplicationStatus.INTERVIEW, ApplicationStatus.ACCEPTED),
        (ApplicationStatus.INTERVIEW, ApplicationStatus.REJECTED),
    ],
)
def test_each_company_transition_is_historized_and_notified(
    student_profile,
    internal_offer,
    previous_status,
    new_status,
):
    interview_at = timezone.now() + timedelta(days=3)
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=previous_status,
        interview_at=(
            interview_at
            if previous_status == ApplicationStatus.INTERVIEW
            else None
        ),
        created_by=student_profile.user,
    )

    updated = ApplicationService.change_status(
        application=application,
        new_status=new_status,
        updated_by=internal_offer.company.user,
        interview_at=(
            interview_at if new_status == ApplicationStatus.INTERVIEW else None
        ),
    )

    assert updated.status == new_status
    history = ApplicationStatusHistory.objects.get(application=application)
    assert history.previous_status == previous_status
    assert history.new_status == new_status
    assert history.changed_by == internal_offer.company.user
    assert Notification.objects.filter(user=student_profile.user).count() == 1


@pytest.mark.parametrize(
    "terminal_status",
    [
        ApplicationStatus.ACCEPTED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    ],
)
def test_terminal_application_statuses_reject_further_transitions(
    student_profile,
    internal_offer,
    terminal_status,
):
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=terminal_status,
        created_by=student_profile.user,
    )

    with pytest.raises(ValidationError):
        ApplicationService.change_status(
            application=application,
            new_status=ApplicationStatus.VIEWED,
            updated_by=internal_offer.company.user,
        )

    application.refresh_from_db()
    assert application.status == terminal_status
    assert not ApplicationStatusHistory.objects.filter(
        application=application,
    ).exists()


def test_notification_failure_rolls_back_status_and_history(
    student_profile,
    internal_offer,
    monkeypatch,
):
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.RECEIVED,
        created_by=student_profile.user,
    )

    def fail_create(**kwargs):
        raise RuntimeError

    monkeypatch.setattr(Notification.objects, "create", fail_create)

    with pytest.raises(RuntimeError):
        ApplicationService.change_status(
            application=application,
            new_status=ApplicationStatus.VIEWED,
            updated_by=internal_offer.company.user,
        )

    application.refresh_from_db()
    assert application.status == ApplicationStatus.RECEIVED
    assert ApplicationStatusHistory.objects.filter(
        application=application,
    ).count() == 0


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
    assert Notification.objects.filter(user=student_profile.user).count() == 1


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
    assert Notification.objects.filter(
        user=internal_offer.company.user,
    ).count() == 1


def test_student_can_withdraw_from_viewed_application(
    student_profile,
    internal_offer,
):
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.VIEWED,
        created_by=student_profile.user,
    )

    withdrawn = ApplicationService.withdraw(
        application=application,
        student=student_profile,
    )

    history = ApplicationStatusHistory.objects.get(application=application)
    assert withdrawn.status == ApplicationStatus.WITHDRAWN
    assert history.previous_status == ApplicationStatus.VIEWED
    assert history.new_status == ApplicationStatus.WITHDRAWN
    assert history.changed_by == student_profile.user
    assert Notification.objects.filter(
        user=internal_offer.company.user,
    ).count() == 1
    with pytest.raises(ValidationError):
        ApplicationService.withdraw(
            application=withdrawn,
            student=student_profile,
            reason="Nouvel essai.",
        )
    assert Notification.objects.filter(
        user=internal_offer.company.user,
    ).count() == 1


def test_notification_failure_rolls_back_withdrawal_and_history(
    student_profile,
    internal_offer,
    monkeypatch,
):
    application = Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.INTERVIEW,
        interview_at=timezone.now() + timedelta(days=3),
        created_by=student_profile.user,
    )

    def fail_create(**kwargs):
        raise RuntimeError

    monkeypatch.setattr(Notification.objects, "create", fail_create)

    with pytest.raises(RuntimeError):
        ApplicationService.withdraw(
            application=application,
            student=student_profile,
            reason="Je ne suis plus disponible.",
        )

    application.refresh_from_db()
    assert application.status == ApplicationStatus.INTERVIEW
    assert ApplicationStatusHistory.objects.filter(
        application=application,
    ).count() == 0


@pytest.mark.parametrize(
    ("interview_offset", "reason"),
    [
        (timedelta(days=2), "   "),
        (timedelta(hours=23), "Motif fourni."),
        (timedelta(hours=0), "Motif fourni."),
        (-timedelta(hours=1), "Motif fourni."),
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
    add_profile_cv(student_profile)
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
    assert Notification.objects.count() == 0


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
    add_profile_cv(student_profile)
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


def test_submission_requires_cv_in_profile(client, student_profile, internal_offer):
    client.force_login(student_profile.user)

    response = client.post(
        reverse("application:submit", kwargs={"offer_pk": internal_offer.pk}),
        {"cover_letter": "Ma motivation."},
    )

    assert response.status_code == HTTPStatus.OK
    assert "Ajoutez un CV à votre profil" in response.content.decode()
    assert not Application.objects.filter(student=student_profile).exists()


def test_application_service_requires_cv(student_profile, internal_offer):
    with pytest.raises(ValidationError, match="Ajoutez un CV"):
        ApplicationService.submit(
            student=student_profile,
            offer=internal_offer,
        )

    assert not Application.objects.filter(student=student_profile).exists()


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


def test_company_application_queryset_avoids_candidate_n_plus_one(
    student_profile,
    internal_offer,
):
    students = [student_profile]
    students.extend(
        [
            StudentProfile.objects.create(
                user=UserFactory(role=Role.STUDENT, email_verified=True),
                field_of_study=f"Domaine {index}",
                level="Licence",
            )
            for index in range(EXPECTED_APPLICATION_LIST_SIZE - 1)
        ],
    )
    for student in students:
        application = Application.objects.create(
            student=student,
            offer=internal_offer,
            created_by=student.user,
        )
        ApplicationStatusHistory.objects.create(
            application=application,
            previous_status="",
            new_status=ApplicationStatus.RECEIVED,
            changed_by=internal_offer.company.user,
        )

    view = CompanyApplicationsView()
    view.request = SimpleNamespace(user=internal_offer.company.user)
    view.profile = internal_offer.company

    with CaptureQueriesContext(connection) as queries:
        applications = list(view.get_queryset())
        candidate_data = [
            (
                application.student.user.name,
                application.offer.title,
                [
                    history.changed_by.name
                    for history in application.status_history.all()
                ],
            )
            for application in applications
        ]

    assert len(candidate_data) == EXPECTED_APPLICATION_LIST_SIZE
    assert len(queries) == EXPECTED_APPLICATION_LIST_QUERY_COUNT


def test_student_application_queryset_avoids_offer_n_plus_one(
    student_profile,
    internal_offer,
):
    offers = [internal_offer]
    offers.extend(
        [
            InternshipOffer.objects.create(
                company=internal_offer.company,
                created_by=internal_offer.company.user,
                title=f"Stage {index}",
                description="Stage de développement.",
                domain="Informatique",
                location="Douala",
                duration_days=30,
                application_deadline=timezone.now() + timedelta(days=15),
                status=OfferStatus.PUBLISHED,
                published_at=timezone.now(),
                application_mode=ApplicationMode.INTERNAL,
            )
            for index in range(EXPECTED_APPLICATION_LIST_SIZE - 1)
        ],
    )
    for offer in offers:
        application = Application.objects.create(
            student=student_profile,
            offer=offer,
            created_by=student_profile.user,
        )
        ApplicationStatusHistory.objects.create(
            application=application,
            previous_status="",
            new_status=ApplicationStatus.RECEIVED,
            changed_by=internal_offer.company.user,
        )

    view = StudentApplicationsView()
    view.profile = student_profile

    with CaptureQueriesContext(connection) as queries:
        applications = list(view.get_queryset())
        offer_data = [
            (
                application.offer.title,
                application.offer.company.company_name,
                [
                    history.changed_by.name
                    for history in application.status_history.all()
                ],
            )
            for application in applications
        ]

    assert len(offer_data) == EXPECTED_APPLICATION_LIST_SIZE
    assert len(queries) == EXPECTED_APPLICATION_LIST_QUERY_COUNT


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
    assert response.context["applications"][0].offer.title in response.content.decode()


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


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="Concurrency guarantees require PostgreSQL row locks.",
)
def test_postgres_concurrent_acceptances_respect_offer_capacity(
    student_profile,
    internal_offer,
):
    second_student = StudentProfile.objects.create(
        user=UserFactory(role=Role.STUDENT, email_verified=True),
        field_of_study="Marketing",
        level="Licence",
    )
    applications = [
        Application.objects.create(
            student=student,
            offer=internal_offer,
            status=ApplicationStatus.INTERVIEW,
            interview_at=timezone.now() + timedelta(days=3),
            created_by=student.user,
        )
        for student in (student_profile, second_student)
    ]
    barrier = Barrier(2)
    actor_id = internal_offer.company.user_id

    def accept(application_id):
        close_old_connections()
        try:
            application = Application.all_objects.get(pk=application_id)
            actor = get_user_model().objects.get(pk=actor_id)
            barrier.wait(timeout=15)
            try:
                ApplicationService.change_status(
                    application=application,
                    new_status=ApplicationStatus.ACCEPTED,
                    updated_by=actor,
                )
            except ValidationError:
                return False
            return True
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(accept, [app.pk for app in applications]))

    assert sum(results) == 1
    assert Application.all_objects.filter(
        offer=internal_offer,
        status=ApplicationStatus.ACCEPTED,
    ).count() == 1
    assert ApplicationStatusHistory.objects.filter(
        application__in=applications,
        new_status=ApplicationStatus.ACCEPTED,
    ).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="Concurrency guarantees require PostgreSQL row locks.",
)
def test_postgres_capacity_reduction_races_safely_with_acceptance(
    student_profile,
    internal_offer,
):
    internal_offer.available_positions = 2
    internal_offer.save(update_fields=["available_positions"])
    Application.objects.create(
        student=student_profile,
        offer=internal_offer,
        status=ApplicationStatus.ACCEPTED,
        created_by=student_profile.user,
    )
    candidate = StudentProfile.objects.create(
        user=UserFactory(role=Role.STUDENT, email_verified=True),
        field_of_study="Marketing",
        level="Licence",
    )
    application = Application.objects.create(
        student=candidate,
        offer=internal_offer,
        status=ApplicationStatus.INTERVIEW,
        interview_at=timezone.now() + timedelta(days=3),
        created_by=candidate.user,
    )
    actor_id = internal_offer.company.user_id
    offer_id = internal_offer.pk
    barrier = Barrier(2)

    def reduce_capacity():
        close_old_connections()
        try:
            offer = InternshipOffer.all_objects.get(pk=offer_id)
            actor = get_user_model().objects.get(pk=actor_id)
            barrier.wait(timeout=15)
            try:
                update_offer(actor, offer, {"available_positions": 1})
            except ValidationError:
                return "reduction_blocked"
            return "reduced"
        finally:
            close_old_connections()

    def accept_candidate():
        close_old_connections()
        try:
            candidate_application = Application.all_objects.get(pk=application.pk)
            actor = get_user_model().objects.get(pk=actor_id)
            barrier.wait(timeout=15)
            try:
                ApplicationService.change_status(
                    application=candidate_application,
                    new_status=ApplicationStatus.ACCEPTED,
                    updated_by=actor,
                )
            except ValidationError:
                return "acceptance_blocked"
            return "accepted"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                lambda action: action(),
                (reduce_capacity, accept_candidate),
            ),
        )

    internal_offer.refresh_from_db()
    accepted_count = Application.all_objects.filter(
        offer=internal_offer,
        status=ApplicationStatus.ACCEPTED,
    ).count()
    assert accepted_count <= internal_offer.available_positions
    assert set(outcomes) in (
        {"reduced", "acceptance_blocked"},
        {"reduction_blocked", "accepted"},
    )
