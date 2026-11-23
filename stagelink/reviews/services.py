from django.contrib.auth import get_user_model
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
                _("Vous devez être connecté pour laisser un avis."),
            )

        # Serialize submissions for the same account so parallel requests cannot
        # pass the active-review check at the same time. Soft-deleted reviews
        # remain excluded by the default manager, as before.
        user = get_user_model().objects.select_for_update().get(pk=user.pk)
        if Review.objects.filter(user=user).exists():
            raise ValidationError(
                _("Vous avez déjà laissé un avis."),
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

        review = Review.all_objects.select_for_update().get(pk=review.pk)
        require_review_owner(user, review)

        if review.is_deleted:
            raise ValidationError(
                _("Cet avis a été supprimé."),
            )

        review.rating = rating
        review.comment = comment
        review.updated_by = user
        # Any edited text must pass moderation again before public display.
        review.is_approved = False
        review.approved_at = None
        review.approved_by = None

        review.full_clean()
        review.save(
            update_fields=[
                "rating",
                "comment",
                "updated_by",
                "updated_at",
                "is_approved",
                "approved_at",
                "approved_by",
            ],
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

        review = Review.all_objects.select_for_update().get(pk=review.pk)
        require_review_owner(user, review)

        if review.is_deleted:
            raise ValidationError(
                _("Cet avis est déjà supprimé."),
            )

        review.soft_delete(user)

        return review
