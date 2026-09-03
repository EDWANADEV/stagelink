from django.core.exceptions import PermissionDenied


def require_notification_owner(user, notification) -> None:
    """
    Vérifie que la notification appartient à l'utilisateur.
    """

    if not user.is_authenticated:
        raise PermissionDenied

    if notification.user_id != user.id:
        raise PermissionDenied(
            "Vous ne pouvez pas modifier cette notification."
        )