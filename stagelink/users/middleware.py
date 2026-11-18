from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import Resolver404
from django.urls import resolve
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _

from stagelink.profiles.services import has_completed_profile
from stagelink.users.otp_utils import OtpTokenError
from stagelink.users.otp_utils import decode_otp_token
from stagelink.users.services import OtpEmailService
from stagelink.users.services import OtpRateLimitError
from stagelink.users.services import OtpService
from stagelink.utils.enums import OTPType

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest
    from django.http import HttpResponse

    from stagelink.users.models import User


# Clé de session où la vue d'inscription stocke le token OTP en attente.
PENDING_SIGNUP_TOKEN_SESSION_KEY = "pending_signup_token"  # noqa: S105

# Vues accessibles sans e-mail vérifié ni profil complet
# (authentification, vérification OTP, mot de passe oublié).
EXEMPT_URL_NAMES = frozenset(
    {
        "users:signin",
        "users:signup",
        "users:logout",
        "users:verify_otp",
        "users:resend_otp",
        "users:forgot_password",
        "users:reset_password",
        "profiles:complete",
    },
)


class ProfileCompletionMiddleware:
    """
    Oblige les utilisateurs connectés à finaliser leur inscription.

    Tant que l'adresse e-mail n'est pas vérifiée par OTP, l'utilisateur
    est redirigé vers la vue de vérification. Une fois vérifié, il est
    redirigé vers le formulaire de complétion du profil (adapté à son
    rôle) tant que ce profil n'existe pas.

    Les fichiers statiques et médias, l'administration et les vues
    d'authentification et de profil sont exclus afin d'éviter toute
    boucle de redirection.

    Doit être placé après AuthenticationMiddleware et MessageMiddleware.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        # Préfixes d'URL calculés une seule fois au démarrage.
        self.exempt_path_prefixes = tuple(
            prefix
            for prefix in (
                settings.STATIC_URL,
                settings.MEDIA_URL,
                f"/{settings.ADMIN_URL}",
                "/__debug__/",
            )
            if prefix and prefix.startswith("/")
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = request.user

        if not self._should_check(request, user):
            return self.get_response(request)

        if not user.email_verified:
            return self._redirect_to_email_verification(request, user)

        if not has_completed_profile(user):
            messages.info(
                request,
                _("Veuillez compléter votre profil pour continuer."),
            )
            return redirect("profiles:complete")

        return self.get_response(request)

    def _should_check(self, request: HttpRequest, user: User) -> bool:
        """Indique si la requête doit être soumise aux contrôles."""
        # Les visiteurs anonymes et l'équipe d'administration ne sont pas concernés.
        if not user.is_authenticated or user.is_staff:
            return False

        if request.path_info.startswith(self.exempt_path_prefixes):
            return False

        return not self._is_exempt_view(request)

    @staticmethod
    def _is_exempt_view(request: HttpRequest) -> bool:
        """Vérifie si l'URL demandée correspond à une vue exclue."""
        try:
            match = resolve(request.path_info)
        except Resolver404:
            # Laisse Django produire la page 404 habituelle.
            return True

        return match.view_name in EXEMPT_URL_NAMES

    def _redirect_to_email_verification(
        self,
        request: HttpRequest,
        user: User,
    ) -> HttpResponse:
        """Redirige vers la vérification OTP de l'adresse e-mail."""
        token = self._get_pending_signup_token(request, user)

        if token is None:
            token = self._send_new_signup_otp(request, user)

        if token is None:
            # Impossible d'envoyer un nouveau code pour le moment :
            # on déconnecte l'utilisateur pour éviter un accès non vérifié.
            logout(request)
            messages.warning(
                request,
                _(
                    "Votre adresse e-mail n'est pas encore vérifiée. "
                    "Veuillez réessayer dans quelques instants.",
                ),
            )
            return redirect("users:signin")

        messages.info(
            request,
            _("Veuillez vérifier votre adresse e-mail pour continuer."),
        )
        return redirect(
            "users:verify_otp",
            purpose=OTPType.SIGNUP,
            token=token,
        )

    @staticmethod
    def _get_pending_signup_token(
        request: HttpRequest,
        user: User,
    ) -> str | None:
        """
        Récupère le token OTP stocké en session s'il appartient à l'utilisateur.

        Un token expiré reste utilisable : la vue de vérification
        permet alors de demander un nouveau code.
        """
        token = request.session.get(PENDING_SIGNUP_TOKEN_SESSION_KEY)
        if not token:
            return None

        try:
            payload = decode_otp_token(token, OTPType.SIGNUP)
        except OtpTokenError:
            return None

        if payload["user_id"] != str(user.pk):
            return None

        return token

    @staticmethod
    def _send_new_signup_otp(
        request: HttpRequest,
        user: User,
    ) -> str | None:
        """
        Génère et envoie un nouveau code OTP d'inscription.

        Retourne None si l'envoi est bloqué par la limitation de fréquence.
        """
        try:
            otp, token = OtpService.create(
                user=user,
                otp_type=OTPType.SIGNUP,
            )
        except OtpRateLimitError:
            return None

        OtpEmailService.send(
            user=user,
            otp=otp,
            language=get_language_from_request(request),
        )
        request.session[PENDING_SIGNUP_TOKEN_SESSION_KEY] = token
        return token
