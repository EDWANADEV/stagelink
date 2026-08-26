
from django.db import models


class SoftDeleteManager(models.Manager):
    """Return only non-deleted objects by default."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """Return all objects, including soft-deleted ones."""

    def get_queryset(self):
        return super().get_queryset()

