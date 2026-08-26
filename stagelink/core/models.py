
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .managers import AllObjectsManager
from .managers import SoftDeleteManager

if TYPE_CHECKING:
    from stagelink.users.models import User


class BaseModel(models.Model):
    """
    Abstract base model for StageLink.

    Provides:
    - UUID primary key
    - creation/update timestamps
    - creation/update audit information
    - soft deletion
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
    )

    created_at = models.DateTimeField(
        _("Date de création"),
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        _("Date de modification"),
        auto_now=True,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        verbose_name=_("Créé par"),
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_updated",
        verbose_name=_("Modifié par"),
    )

    is_deleted = models.BooleanField(
        _("Supprimé"),
        default=False,
        db_index=True,
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def soft_delete(self, user: User | None = None) -> None:
        """Soft-delete this instance."""
        self.is_deleted = True
        self.updated_by = user
        self.save(
            update_fields=[
                "is_deleted",
                "updated_by",
                "updated_at",
            ],
        )

    def restore(self, user: User | None = None) -> None:
        """Restore a soft-deleted instance."""
        self.is_deleted = False
        self.updated_by = user
        self.save(
            update_fields=[
                "is_deleted",
                "updated_by",
                "updated_at",
            ],
        )

    def __str__(self) -> str:
        return f"{self.__class__.__name__} ({self.pk})"

