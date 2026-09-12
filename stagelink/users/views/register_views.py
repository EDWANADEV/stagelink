from django.contrib import messages
from django.db import IntegrityError
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from mtc_web.users.forms import SignupForm
from mtc_web.users.mixins import RedirectToNextOrReferrerMixin
from mtc_web.users.services import OtpEmailService
from mtc_web.users.services import OtpRateLimitError
from mtc_web.users.services import OtpService
from mtc_web.utils.enums import OtpPurpose


class SignupView(RedirectToNextOrReferrerMixin, FormView):
    template_name = "home/pages/auth/signup.html"
    form_class = SignupForm

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.save()
                otp, token = OtpService.create(user, OtpPurpose.SIGNUP)
                OtpEmailService.send(user, otp, language=get_language_from_request(self.request))
        except IntegrityError:
            form.add_error("email", _("Un compte existe déjà avec cette adresse e-mail."))
            messages.error(self.request, _("Veuillez corriger les informations d'inscription."))
            return self.form_invalid(form)
        except OtpRateLimitError as error:
            messages.warning(self.request, error)
            return self.form_invalid(form)

        self.request.session["pending_signup_token"] = token
        messages.success(self.request, _("Votre compte a été créé. Entrez le code reçu par e-mail pour l'activer."))
        return redirect("users:verify_otp", purpose=OtpPurpose.SIGNUP, token=token)

    def form_invalid(self, form):
        messages.error(self.request, _("Veuillez corriger les informations d'inscription."))
        return super().form_invalid(form)
