from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from stagelink.core.models import BaseModel
from stagelink.utils.enums import NotificationType

from .managers import NotificationManager


class Notification(BaseModel):
    """Notification envoyée à un utilisateur."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("Utilisateur"),
    )

    notification_type = models.CharField(
        _("Type"),
        max_length=30,
        choices=NotificationType.choices,
    )

    message = models.TextField(
        _("Message"),
    )

    is_read = models.BooleanField(
        _("Lue"),
        default=False,
    )

    objects = NotificationManager()

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "is_read"],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.notification_type}"