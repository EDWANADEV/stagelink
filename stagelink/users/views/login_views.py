from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from django.views.generic import RedirectView

from stagelink.users.forms import SigninForm
from stagelink.users.mixins import AnonymousRequiredMixin
from stagelink.users.mixins import RedirectToNextOrReferrerMixin


class SigninView(
    AnonymousRequiredMixin,
    RedirectToNextOrReferrerMixin,
    FormView,
):
    """
    Vue de connexion des utilisateurs StageLink.

    Après connexion, ProfileCompletionMiddleware redirige l'utilisateur
    vers la vérification OTP ou la complétion du profil si nécessaire.
    """

    template_name = "users/login.html"
    form_class = SigninForm

    def get_success_url(self):
        # Le paramètre "next" n'est suivi que s'il pointe vers ce site
        # (protection contre les redirections ouvertes).
        return self.get_next_url() or resolve_url(settings.LOGIN_REDIRECT_URL)

    def form_valid(self, form):
        user = form.get_user()

        login(self.request, user)

        if not form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(0)

        messages.success(
            self.request,
            _("Connexion réussie."),
        )

        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(
            self.request,
            _("Veuillez corriger les informations de connexion."),
        )

        return super().form_invalid(form)


class UserRedirectView(LoginRequiredMixin, RedirectView):
    """
    Redirection après authentification vers le tableau de bord.

    Si l'inscription n'est pas finalisée, ProfileCompletionMiddleware
    intercepte la requête avant d'atteindre le tableau de bord.
    """

    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse("profiles:dashboard")


class UserLogoutView(LogoutView):
    """
    Déconnexion sécurisée de l'utilisateur.
    """

    next_page = "users:signin"
