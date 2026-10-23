from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from django.views.generic import TemplateView

from stagelink.profiles.forms import PROFILE_FORM_BY_ROLE
from stagelink.profiles.services import get_dashboard_data
from stagelink.profiles.services import get_profile
from stagelink.profiles.services import has_completed_profile
from stagelink.profiles.services import save_profile


class ProfileCompletionView(LoginRequiredMixin, FormView):
    """
    Complétion (puis modification) du profil de l'utilisateur connecté.

    Le formulaire affiché dépend du rôle : étudiant ou entreprise.
    Tant que ce formulaire n'est pas validé, ProfileCompletionMiddleware
    redirige l'utilisateur ici.
    """

    template_name = "profiles/profile_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            # Profil récupéré une seule fois pour toute la requête.
            self.profile = get_profile(request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_form_class(self):
        """Sélectionne le formulaire correspondant au rôle de l'utilisateur."""
        form_class = PROFILE_FORM_BY_ROLE.get(self.request.user.role)
        if form_class is None:
            raise Http404
        return form_class

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.profile
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_completion"] = self.profile is None
        return context

    def form_valid(self, form):
        is_completion = self.profile is None
        save_profile(self.request.user, form)

        if is_completion:
            messages.success(
                self.request,
                _("Votre profil est complet. Bienvenue sur StageLink !"),
            )
        else:
            messages.success(
                self.request,
                _("Votre profil a été mis à jour."),
            )
        return redirect("profiles:dashboard")

    def form_invalid(self, form):
        messages.error(
            self.request,
            _("Veuillez corriger les erreurs du formulaire."),
        )
        return super().form_invalid(form)


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Tableau de bord affiché une fois le profil complété.

    Le contenu (statistiques, éléments récents) varie selon le rôle.
    """

    template_name = "profiles/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        # Double sécurité si le middleware est désactivé.
        if request.user.is_authenticated and not has_completed_profile(
            request.user,
        ):
            return redirect("profiles:complete")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_dashboard_data(self.request.user))
        return context
