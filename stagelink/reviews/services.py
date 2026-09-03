from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import Review
from .permissions import require_review_owner


class ReviewService:
    """Services métier liés aux avis de la plateforme."""

    @staticmethod
    @transaction.atomic
    def create_review(
        *,
        user,
        rating,
        comment="",
    ) -> Review:
        """Crée un avis concernant la plateforme StageLink."""

        if not user.is_authenticated:
            raise ValidationError(
                _("Vous devez être connecté pour laisser un avis.")
            )

        if Review.objects.filter(user=user).exists():
            raise ValidationError(
                _("Vous avez déjà laissé un avis.")
            )

        review = Review(
            user=user,
            rating=rating,
            comment=comment,
            created_by=user,
            updated_by=user,
        )

        review.full_clean()
        review.save()

        return review

    @staticmethod
    @transaction.atomic
    def update_review(
        *,
        user,
        review,
        rating,
        comment="",
    ) -> Review:
        """Modifie son propre avis."""

        require_review_owner(user, review)

        if review.is_deleted:
            raise ValidationError(
                _("Cet avis a été supprimé.")
            )

        review.rating = rating
        review.comment = comment
        review.updated_by = user

        review.full_clean()
        review.save(
            update_fields=[
                "rating",
                "comment",
                "updated_by",
                "updated_at",
            ]
        )

        return review

    @staticmethod
    @transaction.atomic
    def delete_review(
        *,
        user,
        review,
    ) -> Review:
        """Supprime son propre avis via le soft delete."""

        require_review_owner(user, review)

        if review.is_deleted:
            raise ValidationError(
                _("Cet avis est déjà supprimé.")
            )

        review.soft_delete(user)

        return review