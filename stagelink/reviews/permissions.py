from django.core.exceptions import PermissionDenied


def require_review_owner(user, review) -> None:
    """
    Vérifie que l'utilisateur connecté est l'auteur de l'avis.
    """

    if not user.is_authenticated:
        raise PermissionDenied

    if review.user_id != user.id:
        raise PermissionDenied(
            "Vous ne pouvez pas modifier cet avis."
        )


def require_review_admin(user) -> None:
    """
    Vérifie que l'utilisateur est administrateur.
    """

    if not user.is_authenticated:
        raise PermissionDenied

    if not user.is_staff:
        raise PermissionDenied