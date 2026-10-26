from __future__ import annotations

from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


class RedirectToNextOrReferrerMixin:
    """
    Gère les redirections sécurisées après une action.
    """

    fallback_url = "users:redirect"

    def is_safe_url(self, url: str | None) -> bool:
        if not url:
            return False

        return url_has_allowed_host_and_scheme(
            url=url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        )

    def get_next_url(self) -> str | None:
        next_url = self.request.GET.get("next")

        if self.is_safe_url(next_url):
            return next_url

        return None

    def get_referrer_url(self) -> str | None:
        referrer = self.request.META.get("HTTP_REFERER")

        if self.is_safe_url(referrer):
            return referrer

        return None

    def get_redirect_url(self) -> str:
        next_url = self.get_next_url()

        if next_url:
            return next_url

        referrer_url = self.get_referrer_url()

        if referrer_url:
            return referrer_url

        return reverse(self.fallback_url)

    def get_success_url(self) -> str:
        return self.get_redirect_url()

    def redirect_after_success(self) -> HttpResponseRedirect:
        return HttpResponseRedirect(
            self.get_success_url()
        )


class AnonymousRequiredMixin:
    """
    Empêche un utilisateur déjà connecté
    d'accéder aux pages réservées aux visiteurs.
    """

    redirect_url = "users:redirect"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.redirect_url)

        return super().dispatch(request, *args, **kwargs)
    