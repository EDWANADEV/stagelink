from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from stagelink.users.forms import (
    ForgotPasswordForm,
    PasswordResetConfirmForm,
)
from stagelink.users.services import OtpEmailService
from stagelink.users.services import OtpRateLimitError
from stagelink.users.services import OtpService
from stagelink.users.services import PasswordResetTokenService
from stagelink.utils.enums import OTPType


User = get_user_model()


class ForgotPasswordView(FormView):
    """
    Démarre le processus de réinitialisation du mot de passe.
    """

    template_name = "users/forgot_password.html"
    form_class = ForgotPasswordForm

    def form_valid(self, form):
        email = form.cleaned_data["email"]

        user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).first()

        if user:
            try:
                otp, token = OtpService.create(
                    user=user,
                    otp_type=OTPType.PASSWORD_RESET,
                )

                OtpEmailService.send(
                    user=user,
                    otp=otp,
                    language=get_language_from_request(
                        self.request,
                    ),
                )

            except OtpRateLimitError as error:
                messages.warning(
                    self.request,
                    error,
                )

                return self.form_invalid(form)

            self.request.session[
                "pending_password_reset_token"
            ] = token

            messages.info(
                self.request,
                _(
                    "Un code de réinitialisation "
                    "vous a été envoyé."
                ),
            )

            return redirect(
                "users:verify_otp",
                purpose=OTPType.PASSWORD_RESET,
                token=token,
            )

        # Ne révèle pas si l'adresse existe.
        messages.info(
            self.request,
            _(
                "Si cette adresse e-mail correspond "
                "à un compte, un code de réinitialisation "
                "vous a été envoyé."
            ),
        )

        return redirect("users:signin")

    def form_invalid(self, form):
        messages.error(
            self.request,
            _("Veuillez saisir une adresse e-mail valide."),
        )

        return super().form_invalid(form)


class ResetPasswordView(FormView):
    """
    Définit un nouveau mot de passe après vérification OTP.
    """

    template_name = "users/reset_password.html"
    form_class = PasswordResetConfirmForm

    def dispatch(self, request, *args, **kwargs):
        self.token = kwargs.get("token")

        self.user_id = (
            PasswordResetTokenService.get_user_id(
                self.token,
            )
        )

        if not self.user_id:
            messages.error(
                request,
                _(
                    "Cette demande de réinitialisation "
                    "a expiré ou est invalide."
                ),
            )

            return redirect(
                "users:forgot_password",
            )

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        user = User.objects.filter(
            pk=self.user_id,
        ).first()

        kwargs["user"] = user

        return kwargs

    def get_initial(self):
        return {
            "token": self.token,
        }

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(
                    pk=self.user_id,
                )

                user.set_password(
                    form.cleaned_data["password1"],
                )

                user.save(
                    update_fields=["password"],
                )

                PasswordResetTokenService.delete(
                    self.token,
                )

        except User.DoesNotExist:
            messages.error(
                self.request,
                _("Utilisateur introuvable."),
            )

            return redirect(
                "users:forgot_password",
            )

        messages.success(
            self.request,
            _(
                "Votre mot de passe a été mis à jour. "
                "Vous pouvez maintenant vous connecter."
            ),
        )

        return redirect(
            "users:signin",
        )

    def form_invalid(self, form):
        messages.error(
            self.request,
            _(
                "Veuillez corriger les erreurs "
                "du nouveau mot de passe."
            ),
        )

        return super().form_invalid(form)