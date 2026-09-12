from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView

from mtc_web.users.forms import OtpVerificationForm
from mtc_web.users.mixins import RedirectToNextOrReferrerMixin
from mtc_web.users.services import OtpEmailService
from mtc_web.users.services import OtpRateLimitError
from mtc_web.users.services import OtpService
from mtc_web.users.services import OtpVerificationError
from mtc_web.users.services import OtpVerifyService
from mtc_web.users.services import PasswordResetTokenService
from mtc_web.utils.enums import OtpPurpose


class VerifyOtpView(RedirectToNextOrReferrerMixin, FormView):
    template_name = "home/pages/auth/verify_otp.html"
    form_class = OtpVerificationForm

    def dispatch(self, request, *args, **kwargs):
        self.purpose = kwargs["purpose"]
        self.token = kwargs["token"]
        if self.purpose not in {OtpPurpose.SIGNUP, OtpPurpose.LOGIN, OtpPurpose.PASSWORD_RESET}:
            messages.error(request, _("Cette vérification n'est pas disponible."))
            return redirect("users:signin")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {"token": self.token}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["purpose"] = self.purpose
        context["token"] = self.token
        context["title"] = _("Vérifier votre compte")
        context["subtitle"] = _("Entrez le code à 6 chiffres envoyé dans votre boîte e-mail.")
        if self.purpose == OtpPurpose.PASSWORD_RESET:
            context["title"] = _("Vérifier le code de réinitialisation")
            context["subtitle"] = _("Entrez le code reçu pour créer un nouveau mot de passe.")
        return context

    def form_valid(self, form):
        try:
            otp = OtpVerifyService.verify(
                token=form.cleaned_data["token"],
                code=form.cleaned_data["code"],
                purpose=self.purpose,
            )
        except OtpVerificationError as error:
            messages.error(self.request, error)
            return self.form_invalid(form)
        except ValueError as error:
            messages.error(self.request, str(error))
            return self.form_invalid(form)

        user = otp.user
        if self.purpose == OtpPurpose.PASSWORD_RESET:
            reset_token = PasswordResetTokenService.generate(user)
            messages.success(self.request, _("Code vérifié. Créez maintenant votre nouveau mot de passe."))
            return redirect("users:reset_password", token=reset_token)

        login(self.request, user)
        messages.success(self.request, _("Votre compte est maintenant vérifié."))
        return redirect("users:redirect")

    def form_invalid(self, form):
        messages.error(self.request, _("Veuillez vérifier le code saisi."))
        return super().form_invalid(form)


class ResendOtpView(RedirectToNextOrReferrerMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        purpose = kwargs["purpose"]
        token = kwargs["token"]
        try:
            with transaction.atomic():
                otp = OtpVerifyService._resolve_otp(token, purpose)  # noqa: SLF001
                new_otp, new_token = OtpService.create(otp.user, purpose)
                OtpEmailService.send(otp.user, new_otp, language=get_language_from_request(request))
        except (OtpVerificationError, OtpRateLimitError, ValueError) as error:
            messages.error(request, error)
            return redirect("users:verify_otp", purpose=purpose, token=token)

        messages.success(request, _("Un nouveau code vous a été envoyé."))
        return redirect("users:verify_otp", purpose=purpose, token=new_token)
