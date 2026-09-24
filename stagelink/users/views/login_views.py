from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, RedirectView

from stagelink.users.forms import SigninForm
from stagelink.users.mixins import AnonymousRequiredMixin


class SigninView(AnonymousRequiredMixin, FormView):
    """
    Vue de connexion des utilisateurs StageLink.
    """

    template_name = "users/login.html"
    form_class = SigninForm

    def get_success_url(self):
        return (
            self.request.GET.get("next")
            or settings.LOGIN_REDIRECT_URL
        )

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


class UserRedirectView(RedirectView):
    """
    Redirection après authentification.
    """

    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return settings.LOGIN_REDIRECT_URL


class UserLogoutView(LogoutView):
    """
    Déconnexion sécurisée de l'utilisateur.
    """

    next_page = "users:signin"