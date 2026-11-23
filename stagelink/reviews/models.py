from django.conf import settings
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from stagelink.core.models import BaseModel


class Review(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name=_("Utilisateur"),
    )
    rating = models.PositiveSmallIntegerField(
        _("Note"),
        validators=[
            MinValueValidator(settings.REVIEW_MIN_RATING),
            MaxValueValidator(settings.REVIEW_MAX_RATING),
        ],
    )
    comment = models.TextField(
        _("Commentaire"),
        blank=True,
    )
    is_approved = models.BooleanField(
        _("Approuvé pour publication"),
        default=False,
    )
    approved_at = models.DateTimeField(
        _("Date d'approbation"),
        null=True,
        blank=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews_approved",
        verbose_name=_("Modéré par"),
    )

    class Meta:
        verbose_name = _("Avis")
        verbose_name_plural = _("Avis")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} - {self.rating}/{settings.REVIEW_MAX_RATING}"
