from django.db import transaction

from stagelink.notifications.models import Notification


class NotificationService:
    """Services métier liés aux notifications."""

    @staticmethod
    @transaction.atomic
    def mark_as_read(notification: Notification) -> Notification:
        if notification.is_read:
            return notification

        notification.is_read = True
        notification.save(update_fields=["is_read", "updated_at"])

        return notification