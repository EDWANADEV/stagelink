from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import Review


class ReviewService:
    @staticmethod
    @transaction.atomic
    def create_review(*, user, rating, comment=""):
        if not user.is_authenticated:
            raise ValidationError(
                _("Vous devez être connecté pour laisser un avis.")
            )

        if Review.objects.filter(user=user).count() >= settings.REVIEW_MAX_PER_USER:
            raise ValidationError(
                _("Vous avez atteint le nombre maximum d'avis autorisés.")
            )

        if not (
            settings.REVIEW_MIN_RATING
            <= rating
            <= settings.REVIEW_MAX_RATING
        ):
            raise ValidationError(
                _(
                    "La note doit être comprise entre %(minimum)s et %(maximum)s."
                )
                % {
                    "minimum": settings.REVIEW_MIN_RATING,
                    "maximum": settings.REVIEW_MAX_RATING,
                }
            )

        return Review.objects.create(
            user=user,
            rating=rating,
            comment=comment,
            created_by=user,
            updated_by=user,
        )

    @staticmethod
    @transaction.atomic
    def update_review(*, review, rating, comment=""):
        if not (
            settings.REVIEW_MIN_RATING
            <= rating
            <= settings.REVIEW_MAX_RATING
        ):
            raise ValidationError(
                _(
                    "La note doit être comprise entre %(minimum)s et %(maximum)s."
                )
                % {
                    "minimum": settings.REVIEW_MIN_RATING,
                    "maximum": settings.REVIEW_MAX_RATING,
                }
            )

        review.rating = rating
        review.comment = comment
        review.updated_by = review.user
        review.save(
            update_fields=[
                "rating",
                "comment",
                "updated_by",
                "updated_at",
            ]
        )

        return review
    