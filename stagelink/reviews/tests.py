from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from threading import Barrier
from unittest.mock import Mock

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import Client
from django.test import RequestFactory
from django.urls import reverse

from stagelink.profiles.models import StudentProfile

from .admin import ReviewAdmin
from .models import Review
from .services import ReviewService
from .views import REVIEWS_PER_PAGE

UPDATED_RATING = 4
ALL_REVIEW_COUNT_AFTER_RECREATION = 2
EXPECTED_REVIEW_COUNT_SECOND_PAGE = 2


@pytest.fixture
def reviewer(db):
    user = get_user_model().objects.create_user(
        email="reviewer@example.com",
        password="test-password",  # noqa: S106
        email_verified=True,
        name="StageLink Reviewer",
    )
    StudentProfile.objects.create(
        user=user,
        field_of_study="Informatique",
        level="Licence 3",
        language="fr",
    )
    return user


def make_reviewer(email):
    user = get_user_model().objects.create_user(
        email=email,
        password="test-password",  # noqa: S106
        email_verified=True,
        name="StageLink Reviewer",
    )
    StudentProfile.objects.create(
        user=user,
        field_of_study="Informatique",
        level="Licence 3",
        language="fr",
    )
    return user


def test_review_is_about_stage_link_and_author_can_update(reviewer):
    review = ReviewService.create_review(
        user=reviewer,
        rating=5,
        comment="La plateforme est simple à utiliser.",
    )

    updated = ReviewService.update_review(
        user=reviewer,
        review=review,
        rating=4,
        comment="La navigation reste claire.",
    )

    assert updated.rating == UPDATED_RATING
    assert updated.comment == "La navigation reste claire."


def test_only_one_active_review_per_user_is_allowed(reviewer):
    ReviewService.create_review(user=reviewer, rating=5)

    with pytest.raises(ValidationError):
        ReviewService.create_review(user=reviewer, rating=4)

    assert Review.objects.filter(user=reviewer).count() == 1


def test_review_submission_waits_for_moderation_and_edit_resets_approval(reviewer):
    review = ReviewService.create_review(user=reviewer, rating=5, comment="Avant")
    assert review.is_approved is False

    moderator = get_user_model().objects.create_superuser(
        email="moderator@example.com",
        password="test-password",  # noqa: S106
    )
    request = RequestFactory().post("/admin/")
    request.user = moderator
    request._messages = Mock()  # noqa: SLF001
    ReviewAdmin(Review, AdminSite()).approve_reviews(
        request,
        Review.objects.filter(pk=review.pk),
    )
    review.refresh_from_db()
    assert review.is_approved is True
    assert review.approved_by_id == moderator.pk
    assert review.approved_at is not None

    ReviewService.update_review(
        user=reviewer,
        review=review,
        rating=4,
        comment="Après modification",
    )
    review.refresh_from_db()
    assert review.is_approved is False
    assert review.approved_at is None
    assert review.approved_by_id is None


def test_public_review_list_only_shows_approved_stage_link_reviews(reviewer):
    pending = ReviewService.create_review(
        user=reviewer,
        rating=5,
        comment="Pending review",
    )
    published = Review.all_objects.create(
        user=make_reviewer("published-reviewer@example.com"),
        rating=4,
        comment="<script>safe_to_escape()</script>",
        is_approved=True,
    )

    response = Client().get(reverse("reviews:list"))

    assert response.status_code == HTTPStatus.OK
    assert list(response.context["reviews"]) == [published]
    assert b"<script>safe_to_escape()</script>" not in response.content
    assert b"&lt;script&gt;safe_to_escape()&lt;/script&gt;" in response.content
    assert pending.is_approved is False


def test_review_create_view_requires_login_and_creates_pending_review(reviewer):
    client = Client()
    response = client.get(reverse("reviews:create"))
    assert response.status_code == HTTPStatus.FOUND

    client.force_login(reviewer)
    response = client.post(
        reverse("reviews:create"),
        {"rating": "5", "comment": "Expérience positive de StageLink."},
    )
    assert response.status_code == HTTPStatus.FOUND
    created = Review.objects.get(user=reviewer)
    assert created.is_approved is False


def test_review_create_view_validates_rating_and_ownership(reviewer):
    client = Client()
    client.force_login(reviewer)
    response = client.post(
        reverse("reviews:create"),
        {"rating": "99", "comment": "Texte"},
    )
    assert response.status_code == HTTPStatus.OK
    assert Review.objects.filter(user=reviewer).count() == 0

    review = ReviewService.create_review(user=reviewer, rating=5)
    another_user = make_reviewer("other-review-owner@example.com")
    client.force_login(another_user)
    assert (
        client.get(reverse("reviews:update", args=[review.pk])).status_code
        == HTTPStatus.NOT_FOUND
    )
    assert (
        client.post(reverse("reviews:delete", args=[review.pk])).status_code
        == HTTPStatus.NOT_FOUND
    )


def test_review_update_and_delete_views_preserve_soft_delete(reviewer):
    review = ReviewService.create_review(user=reviewer, rating=3, comment="Initial")
    client = Client()
    client.force_login(reviewer)

    response = client.post(
        reverse("reviews:update", args=[review.pk]),
        {"rating": "4", "comment": "Updated"},
    )
    assert response.status_code == HTTPStatus.FOUND
    review.refresh_from_db()
    assert review.rating == UPDATED_RATING
    assert review.comment == "Updated"
    assert review.is_approved is False

    confirm = client.get(reverse("reviews:delete", args=[review.pk]))
    assert confirm.status_code == HTTPStatus.OK
    deleted = client.post(reverse("reviews:delete", args=[review.pk]))
    assert deleted.status_code == HTTPStatus.FOUND
    review.refresh_from_db()
    assert review.is_deleted is True


def test_review_delete_requires_csrf_token(reviewer):
    review = ReviewService.create_review(user=reviewer, rating=5)
    client = Client(enforce_csrf_checks=True)
    client.force_login(reviewer)

    response = client.post(reverse("reviews:delete", args=[review.pk]))
    assert response.status_code == HTTPStatus.FORBIDDEN
    review.refresh_from_db()
    assert review.is_deleted is False


@pytest.mark.django_db
def test_my_reviews_history_is_paginated():
    user = make_reviewer("review-history@example.com")
    for index in range(11):
        review = ReviewService.create_review(user=user, rating=5, comment=str(index))
        ReviewService.delete_review(user=user, review=review)
    ReviewService.create_review(user=user, rating=4, comment="Actif")

    client = Client()
    client.force_login(user)
    first = client.get(reverse("reviews:mine"))
    second = client.get(reverse("reviews:mine"), {"page": 2})

    assert first.status_code == HTTPStatus.OK
    assert first.context["is_paginated"] is True
    assert len(first.context["reviews"]) == REVIEWS_PER_PAGE
    assert second.status_code == HTTPStatus.OK
    assert len(second.context["reviews"]) == EXPECTED_REVIEW_COUNT_SECOND_PAGE


def test_rating_limits_are_validated(reviewer):
    for rating in (0, 6):
        with pytest.raises(ValidationError):
            ReviewService.create_review(user=reviewer, rating=rating)


def test_only_author_can_edit_or_delete_review(reviewer):
    review = ReviewService.create_review(user=reviewer, rating=5)
    another_user = make_reviewer("other-reviewer@example.com")

    with pytest.raises(PermissionDenied):
        ReviewService.update_review(user=another_user, review=review, rating=1)
    with pytest.raises(PermissionDenied):
        ReviewService.delete_review(user=another_user, review=review)


def test_soft_deleted_review_does_not_count_as_active_duplicate(reviewer):
    review = ReviewService.create_review(user=reviewer, rating=5)
    ReviewService.delete_review(user=reviewer, review=review)

    replacement = ReviewService.create_review(user=reviewer, rating=4)

    assert replacement.pk != review.pk
    assert Review.objects.filter(user=reviewer).count() == 1
    assert (
        Review.all_objects.filter(user=reviewer).count()
        == ALL_REVIEW_COUNT_AFTER_RECREATION
    )


@pytest.mark.django_db(transaction=True)
def test_concurrent_submissions_cannot_create_two_active_reviews():
    user = get_user_model().objects.create_user(
        email="concurrent-reviewer@example.com",
        password="test-password",  # noqa: S106
    )
    barrier = Barrier(2)

    def submit(rating):
        close_old_connections()
        barrier.wait(timeout=5)
        try:
            ReviewService.create_review(user=user, rating=rating)
        except ValidationError:
            return "duplicate"
        else:
            return "created"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, (4, 5)))

    assert sorted(results) == ["created", "duplicate"]
    assert Review.objects.filter(user=user).count() == 1
