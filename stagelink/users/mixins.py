from django.http import HttpResponseRedirect
from django.urls import Resolver404
from django.urls import resolve
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import View


class RedirectToNextOrReferrerMixin:
    """
    Mixin qui redirige vers :
    1. Le paramètre `?next=` (si présent et sûr),
    2. Sinon le référent (`HTTP_REFERER`) s'il est interne,
    3. Sinon une URL fallback (par défaut la home).
    """

    fallback_url = "company:home"

    def is_safe_url(self, url):
        """Vérifie que l'URL est interne (pas d'open redirect)."""
        return url_has_allowed_host_and_scheme(
            url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        )

    def get_redirect_url(self):
        """
        Retourne l'URL de redirection prioritaire.
        Surchargez cette méthode dans les vues qui ont un `next` spécifique.
        """
        next_url = self.request.GET.get("next")
        if next_url and self.is_safe_url(next_url):
            return next_url

        referrer = self.request.META.get("HTTP_REFERER")
        if referrer and self.is_safe_url(referrer):
            return referrer

        return reverse(self.fallback_url)

    def dispatch(self, request, *args, **kwargs):
        """
        Si vous souhaitez rediriger AVANT d'exécuter la vue (par exemple
        pour les vues d'authentification où l'utilisateur est déjà connecté),
        surchargez cette méthode. Sinon, utilisez `get_success_url()` pour
        les redirections après succès.
        """
        # Exemple : rediriger automatiquement si déjà connecté
        if self.request.user.is_authenticated:
            return HttpResponseRedirect(self.get_redirect_url())
        return super().dispatch(request, *args, **kwargs)

    # Méthode utilisée par FormView après un formulaire valide
    def get_success_url(self):
        return self.get_redirect_url()
