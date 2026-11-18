from __future__ import annotations

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from stagelink.users.forms import SignupForm
from stagelink.users.mixins import AnonymousRequiredMixin
from stagelink.users.services import (
    OtpEmailService,
    OtpRateLimitError,
    OtpService,
)
from stagelink.utils.enums import OTPType


class SignupView(AnonymousRequiredMixin, FormView):
    """
    Crée un compte StageLink et démarre la vérification
    de l'adresse e-mail.
    """

    template_name = "users/signup.html"
    form_class = SignupForm

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.save()

                otp, token = OtpService.create(
                    user=user,
                    otp_type=OTPType.SIGNUP,
                )

                OtpEmailService.send(
                    user=user,
                    otp=otp,
                    language=get_language_from_request(
                        self.request,
                    ),
                )

        except IntegrityError:
            form.add_error(
                "email",
                _(
                    "Un compte existe déjà avec cette "
                    "adresse e-mail."
                ),
            )

            return self.form_invalid(form)

        except OtpRateLimitError as error:
            messages.warning(
                self.request,
                str(error),
            )

            return self.form_invalid(form)

        self.request.session["pending_signup_token"] = token

        messages.success(
            self.request,
            _(
                "Votre compte a été créé. "
                "Entrez le code reçu par e-mail pour le vérifier."
            ),
        )

        return redirect(
            "users:verify_otp",
            purpose=OTPType.SIGNUP,
            token=token,
        )

    def form_invalid(self, form):
        return super().form_invalid(form)