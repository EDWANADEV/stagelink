from django.core.exceptions import PermissionDenied


def require_payment_owner(user, payment) -> None:
    """Vérifie que l'utilisateur possède le paiement."""

    if not user.is_authenticated:
        raise PermissionDenied

    if payment.donation.donor_id != user.id:
        raise PermissionDenied(
            "Vous ne pouvez pas accéder à ce paiement."
        )


def require_payment_admin(user) -> None:
    """Vérifie que l'utilisateur est administrateur."""

    if not user.is_authenticated:
        raise PermissionDenied

    if not user.is_staff:
        raise PermissionDenied