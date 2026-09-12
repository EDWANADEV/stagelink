from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from django.views.generic import RedirectView

from mtc_web.users.forms import SigninForm
from mtc_web.users.mixins import RedirectToNextOrReferrerMixin
from mtc_web.users.services import OtpEmailService
from mtc_web.users.services import OtpRateLimitError
from mtc_web.users.services import OtpService
from mtc_web.utils.enums import OtpPurpose


class SigninView(RedirectToNextOrReferrerMixin, FormView):
    template_name = "home/pages/auth/signin.html"
    form_class = SigninForm

    def get_success_url(self):
        return self.request.GET.get("next") or reverse(settings.LOGIN_REDIRECT_URL)

    def form_valid(self, form):
        user = form.user
        if not user.is_verified:
            try:
                otp, token = OtpService.create(user, OtpPurpose.LOGIN)
                OtpEmailService.send(user, otp, language=get_language_from_request(self.request))
            except OtpRateLimitError as error:
                messages.warning(self.request, error)
                return redirect("users:verify_otp", purpose=OtpPurpose.LOGIN, token=self.request.session.get("pending_login_token", ""))

            self.request.session["pending_login_token"] = token
            messages.info(self.request, _("Un code de vérification vous a été envoyé."))
            return redirect("users:verify_otp", purpose=OtpPurpose.LOGIN, token=token)

        login(self.request, user)
        if not form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(0)
        messages.success(self.request, _("Connexion réussie."))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Veuillez corriger les informations de connexion."))
        return super().form_invalid(form)


class UserRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse("company:dashboard")


class UserLogoutView(LogoutView):
    next_page = "company:home"
