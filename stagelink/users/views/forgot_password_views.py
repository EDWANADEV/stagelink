from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from mtc_web.users.forms import ForgotPasswordForm
from mtc_web.users.forms import PasswordResetConfirmForm
from mtc_web.users.mixins import RedirectToNextOrReferrerMixin
from mtc_web.users.services import OtpEmailService
from mtc_web.users.services import OtpRateLimitError
from mtc_web.users.services import OtpService
from mtc_web.users.services import PasswordResetTokenService
from mtc_web.utils.enums import OtpPurpose

User = get_user_model()


class ForgotPasswordView(RedirectToNextOrReferrerMixin, FormView):
    template_name = "home/pages/auth/forgot_password.html"
    form_class = ForgotPasswordForm

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        user = User.objects.filter(email__iexact=email).first()
        if user:
            try:
                otp, token = OtpService.create(user, OtpPurpose.PASSWORD_RESET)
                OtpEmailService.send(user, otp, language=get_language_from_request(self.request))
            except OtpRateLimitError as error:
                messages.warning(self.request, error)
                return self.form_invalid(form)

            self.request.session["pending_password_reset_token"] = token
            messages.info(self.request, _("Un code de réinitialisation vous a été envoyé."))
            return redirect("users:verify_otp", purpose=OtpPurpose.PASSWORD_RESET, token=token)

        messages.info(self.request, _("Si cette adresse existe, un code de réinitialisation a été envoyé."))
        return redirect("users:signin")

    def form_invalid(self, form):
        messages.error(self.request, _("Veuillez saisir une adresse e-mail valide."))
        return super().form_invalid(form)


class ResetPasswordView(RedirectToNextOrReferrerMixin, FormView):
    template_name = "home/pages/auth/reset_password.html"
    form_class = PasswordResetConfirmForm

    def dispatch(self, request, *args, **kwargs):
        self.token = kwargs["token"]
        self.user_id = PasswordResetTokenService.get_user_id(self.token)
        if not self.user_id:
            messages.error(request, _("Cette demande de réinitialisation a expiré."))
            return redirect("users:forgot_password")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {"token": self.token}

    def form_valid(self, form):
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=self.user_id)
            user.set_password(form.cleaned_data["password1"])
            user.is_verified = True
            user.save(update_fields=["password", "is_verified"])
            PasswordResetTokenService.delete(form.cleaned_data["token"])

        messages.success(self.request, _("Votre mot de passe a été mis à jour. Vous pouvez vous connecter."))
        return redirect("users:signin")

    def form_invalid(self, form):
        messages.error(self.request, _("Veuillez corriger le nouveau mot de passe."))
        return super().form_invalid(form)
