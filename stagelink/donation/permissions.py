from django.core.exceptions import PermissionDenied


def require_donation_owner(user, donation) -> None:
    """Vérifie que l'utilisateur connecté est le propriétaire du don."""

    if not user.is_authenticated:
        raise PermissionDenied

    if donation.donor_id != user.id:
        raise PermissionDenied(
            "Vous ne pouvez pas accéder à ce don."
        )


def require_donation_admin(user) -> None:
    """Vérifie que l'utilisateur est administrateur."""

    if not user.is_authenticated:
        raise PermissionDenied

    if not user.is_staff:
        raise PermissionDenied