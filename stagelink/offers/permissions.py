from django.core.exceptions import PermissionDenied

from stagelink.utils.enums import Role


def require_company(user) -> None:
    """
    Vérifie que l'utilisateur est authentifié
    et possède le rôle entreprise.
    """
    if not user.is_authenticated:
        raise PermissionDenied

    if user.role != Role.COMPANY:
        raise PermissionDenied


def require_admin(user) -> None:
    """
    Vérifie que l'utilisateur possède les droits
    d'administration Django.
    """
    if not user.is_authenticated:
        raise PermissionDenied

    if not user.is_staff:
        raise PermissionDenied


def require_offer_owner(user, offer) -> None:
    """
    Vérifie que l'utilisateur est le créateur de l'offre.

    Le propriétaire est déterminé grâce au champ
    created_by hérité de BaseModel.
    """
    if not user.is_authenticated:
        raise PermissionDenied

    if offer.created_by_id != user.id:
        raise PermissionDenied