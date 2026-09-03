from django.core.exceptions import PermissionDenied

from stagelink.utils.enums import Role


def require_student(user) -> None:
    """
    Vérifie que l'utilisateur est authentifié
    et possède le rôle étudiant.
    """
    if not user.is_authenticated:
        raise PermissionDenied

    if user.role != Role.STUDENT:
        raise PermissionDenied


def require_company(user) -> None:
    """
    Vérifie que l'utilisateur est authentifié
    et possède le rôle entreprise.
    """
    if not user.is_authenticated:
        raise PermissionDenied

    if user.role != Role.COMPANY:
        raise PermissionDenied


def require_application_owner(user, application) -> None:
    """
    Vérifie que l'utilisateur est l'étudiant
    propriétaire de la candidature.
    """
    if not user.is_authenticated:
        raise PermissionDenied

    if application.student.user_id != user.id:
        raise PermissionDenied


def require_offer_company(user, application) -> None:
    """
    Vérifie que l'utilisateur est l'entreprise
    propriétaire de l'offre concernée.
    """
    if not user.is_authenticated:
        raise PermissionDenied

    if application.offer.company is None:
        raise PermissionDenied

    if application.offer.company.user_id != user.id:
        raise PermissionDenied