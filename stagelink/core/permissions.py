"""
Contrôle d'accès aux espaces de travail StageLink.

Parcours imposé à chaque utilisateur :
inscription → vérification de l'e-mail → complétion du profil → espace de travail.

Chaque étape ne redirige que vers une étape *antérieure* du parcours,
ce qui garantit l'absence de boucle de redirection.
"""

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse

from stagelink.profiles.models import CompanyProfile
from stagelink.profiles.models import StudentProfile
from stagelink.utils.enums import Role

PROFILE_MODELS = {
    Role.STUDENT: StudentProfile,
    Role.COMPANY: CompanyProfile,
}

DASHBOARD_URLS = {
    Role.STUDENT: "core:student-dashboard",
    Role.COMPANY: "core:company-dashboard",
}

PROFILE_COMPLETE_URLS = {
    Role.STUDENT: "profiles:student-complete",
    Role.COMPANY: "profiles:company-complete",
}


def get_profile(user):
    """Retourne le profil (non supprimé) correspondant au rôle, ou None."""
    model = PROFILE_MODELS.get(user.role)

    if model is None:
        return None

    return model.objects.filter(user=user).first()


def get_workspace_url(user) -> str:
    """Retourne l'URL de la prochaine étape du parcours de l'utilisateur."""
    if user.is_staff and get_profile(user) is None:
        return reverse("admin:index")

    if not user.email_verified:
        return reverse("users:verify-email")

    if get_profile(user) is None:
        return reverse(PROFILE_COMPLETE_URLS[user.role])

    return reverse(DASHBOARD_URLS[user.role])


class RoleRequiredMixin(AccessMixin):
    """
    Vérifie côté serveur :
    - que l'utilisateur est connecté (sinon : page de connexion) ;
    - qu'il possède le rôle attendu (sinon : erreur 403) ;
    - que son adresse e-mail est vérifiée (sinon : page de vérification).
    """

    required_role: str | None = None

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return self.handle_no_permission()

        if self.required_role and user.role != self.required_role:
            raise PermissionDenied

        if not user.email_verified:
            return redirect("users:verify-email")

        return super().dispatch(request, *args, **kwargs)


class WorkspaceRequiredMixin(RoleRequiredMixin):
    """
    Accès à l'espace de travail : en plus des contrôles de
    RoleRequiredMixin, le profil du rôle doit être complété.

    Le profil est exposé dans self.profile pour les vues.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.email_verified:
            self.profile = get_profile(request.user)

            if self.profile is None and (
                self.required_role is None or request.user.role == self.required_role
            ):
                return redirect(PROFILE_COMPLETE_URLS[request.user.role])

        return super().dispatch(request, *args, **kwargs)


class StudentRequiredMixin(WorkspaceRequiredMixin):
    required_role = Role.STUDENT


class CompanyRequiredMixin(WorkspaceRequiredMixin):
    required_role = Role.COMPANY
