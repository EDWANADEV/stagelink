from http import HTTPStatus

import pytest
from django.urls import reverse

from stagelink.notifications.models import Notification
from stagelink.profiles.models import StudentProfile
from stagelink.users.tests.factories import UserFactory
from stagelink.utils.enums import NotificationType
from stagelink.utils.enums import Role

pytestmark = pytest.mark.django_db


def make_notification(user, message="Mise à jour StageLink"):
    return Notification.objects.create(
        user=user,
        notification_type=NotificationType.SYSTEM,
        message=message,
        created_by=user,
    )


def make_student_user():
    user = UserFactory(role=Role.STUDENT, email_verified=True)
    StudentProfile.objects.create(
        user=user,
        field_of_study="Informatique",
        level="Licence",
    )
    return user


def test_notification_list_only_shows_current_users_notifications(client):
    user = make_student_user()
    own = make_notification(user, "Ma notification")
    make_notification(make_student_user(), "Notification privée")
    client.force_login(user)

    response = client.get(reverse("notifications:list"))

    assert response.status_code == HTTPStatus.OK
    assert list(response.context["notifications"]) == [own]
    assert "Notification privée".encode() not in response.content


def test_owner_can_mark_notification_read(client):
    user = make_student_user()
    notification = make_notification(user)
    client.force_login(user)

    response = client.post(
        reverse("notifications:read", kwargs={"pk": notification.pk}),
    )

    notification.refresh_from_db()
    assert response.status_code == HTTPStatus.FOUND
    assert notification.is_read
    assert notification.updated_by == user


def test_user_cannot_mark_another_users_notification_read(client):
    owner = make_student_user()
    other = make_student_user()
    notification = make_notification(owner)
    client.force_login(other)

    response = client.post(
        reverse("notifications:read", kwargs={"pk": notification.pk}),
    )

    notification.refresh_from_db()
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not notification.is_read


def test_mark_notification_read_rejects_get(client):
    user = make_student_user()
    notification = make_notification(user)
    client.force_login(user)

    response = client.get(
        reverse("notifications:read", kwargs={"pk": notification.pk}),
    )

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
