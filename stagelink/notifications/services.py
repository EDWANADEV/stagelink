from django.core.exceptions import PermissionDenied
from django.db import transaction

from stagelink.notifications.models import Notification


class NotificationService:
    """Services métier liés aux notifications."""

    @staticmethod
    def create_on_commit(*, recipient_id, notification_type, message) -> None:
        """Crée une notification in-app uniquement après le commit métier."""
        if recipient_id is None:
            return

        def create_notification():
            Notification.objects.create(
                user_id=recipient_id,
                notification_type=notification_type,
                message=message,
            )

        transaction.on_commit(create_notification, robust=True)

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
            raise PermissionDenied

        if notification.is_read:
            return notification

        notification.is_read = True
        notification.updated_by = user

        notification.save(
            update_fields=[
                "is_read",
                "updated_by",
                "updated_at",
            ],
        )

        return notification
