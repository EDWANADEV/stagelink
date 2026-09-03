from django.core.exceptions import PermissionDenied
from django.db import transaction

from stagelink.notifications.models import Notification


class NotificationService:
    """Services métier liés aux notifications."""

    @staticmethod
    @transaction.atomic
    def mark_as_read(
        notification: Notification,
        user,
    ) -> Notification:
        """
        Marque une notification comme lue.

        Seul le propriétaire de la notification
        peut effectuer cette action.
        """

        if not user.is_authenticated:
            raise PermissionDenied

        if notification.user_id != user.id:
            raise PermissionDenied(
                "Vous ne pouvez pas modifier cette notification."
            )

        if notification.is_read:
            return notification

        notification.is_read = True
        notification.updated_by = user

        notification.save(
            update_fields=[
                "is_read",
                "updated_by",
                "updated_at",
            ]
        )

        return notification