from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Count
from django.db.models import Q

from stagelink.application.models import Application
from stagelink.offers.models import InternshipOffer
from stagelink.utils.enums import ApplicationStatus
from stagelink.utils.enums import OfferStatus
from stagelink.utils.enums import Role

from .models import CompanyProfile
from .models import StudentProfile

if TYPE_CHECKING:
    from django.forms import ModelForm

    from stagelink.users.models import User

# Modèle de profil associé à chaque rôle.
PROFILE_MODEL_BY_ROLE = {
    Role.STUDENT: StudentProfile,
    Role.COMPANY: CompanyProfile,
}

# Nombre d'éléments récents affichés sur le tableau de bord.
DASHBOARD_RECENT_ITEMS = 5


def get_profile(user: User) -> StudentProfile | CompanyProfile | None:
    """
    Retourne le profil actif de l'utilisateur selon son rôle.

    Le manager par défaut ignore les profils supprimés de façon logique.
    """
    profile_model = PROFILE_MODEL_BY_ROLE.get(user.role)
    if profile_model is None:
        return None

    return profile_model.objects.select_related("user").filter(user=user).first()


def has_completed_profile(user: User) -> bool:
    """
    Indique si l'utilisateur a complété le profil correspondant à son rôle.

    Une seule requête EXISTS est exécutée. Les rôles sans profil
    sont considérés comme complets.
    """
    profile_model = PROFILE_MODEL_BY_ROLE.get(user.role)
    if profile_model is None:
        return True

    return profile_model.objects.filter(user_id=user.pk).exists()


@transaction.atomic
def save_profile(user: User, form: ModelForm) -> StudentProfile | CompanyProfile:
    """
    Enregistre le profil validé et rattache l'utilisateur.

    Une fois le profil enregistré, ProfileCompletionMiddleware
    lève automatiquement la restriction d'accès.
    """
    is_creation = form.instance.pk is None

    profile = form.save(commit=False)
    profile.user = user
    if is_creation:
        profile.created_by = user
    profile.updated_by = user
    profile.save()

    # Le nom complet de l'étudiant est stocké sur User.
    name = form.cleaned_data.get("name")
    if name and name != user.name:
        user.name = name
        user.save(update_fields=["name"])

    return profile


def get_student_dashboard_data(profile: StudentProfile) -> dict:
    """Prépare les statistiques et candidatures récentes d'un étudiant."""
    applications = Application.objects.filter(student=profile)

    stats = applications.aggregate(
        total=Count("id"),
        in_progress=Count(
            "id",
            filter=Q(
                status__in=[
                    ApplicationStatus.RECEIVED,
                    ApplicationStatus.VIEWED,
                    ApplicationStatus.INTERVIEW,
                ],
            ),
        ),
        accepted=Count("id", filter=Q(status=ApplicationStatus.ACCEPTED)),
    )

    # select_related évite une requête par offre et par entreprise (N+1).
    recent_applications = applications.select_related(
        "offer",
        "offer__company",
    ).order_by("-created_at")[:DASHBOARD_RECENT_ITEMS]

    return {
        "stats": stats,
        "recent_applications": recent_applications,
    }


def get_company_dashboard_data(profile: CompanyProfile) -> dict:
    """Prépare les statistiques et offres récentes d'une entreprise."""
    offers = InternshipOffer.objects.filter(company=profile)

    stats = offers.aggregate(
        total=Count("id"),
        published=Count("id", filter=Q(status=OfferStatus.PUBLISHED)),
        draft=Count("id", filter=Q(status=OfferStatus.DRAFT)),
    )
    stats["applications"] = Application.objects.filter(
        offer__company=profile,
    ).count()

    # Le nombre de candidatures est calculé dans la même requête (N+1).
    recent_offers = offers.annotate(
        applications_count=Count(
            "applications",
            filter=Q(applications__is_deleted=False),
        ),
    ).order_by("-created_at")[:DASHBOARD_RECENT_ITEMS]

    return {
        "stats": stats,
        "recent_offers": recent_offers,
    }


def get_dashboard_data(user: User) -> dict:
    """
    Construit le contexte du tableau de bord selon le rôle.

    Retourne un dictionnaire vide si l'utilisateur n'a pas de profil.
    """
    profile = get_profile(user)
    if profile is None:
        return {}

    if user.role == Role.STUDENT:
        data = get_student_dashboard_data(profile)
    else:
        data = get_company_dashboard_data(profile)

    data["profile"] = profile
    return data
