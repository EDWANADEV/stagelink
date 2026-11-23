from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import close_old_connections

from .models import Review
from .services import ReviewService

UPDATED_RATING = 4
ALL_REVIEW_COUNT_AFTER_RECREATION = 2


@pytest.fixture
def reviewer(db):
    return get_user_model().objects.create_user(
        email="reviewer@example.com",
        password="test-password",  # noqa: S106
    )


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


def test_rating_limits_are_validated(reviewer):
    for rating in (0, 6):
        with pytest.raises(ValidationError):
            ReviewService.create_review(user=reviewer, rating=rating)


def test_only_author_can_edit_or_delete_review(reviewer):
    review = ReviewService.create_review(user=reviewer, rating=5)
    another_user = get_user_model().objects.create_user(
        email="other-reviewer@example.com",
        password="test-password",  # noqa: S106
    )

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
