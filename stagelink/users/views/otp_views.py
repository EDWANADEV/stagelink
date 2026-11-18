from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect
from django.utils.translation import get_language_from_request
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView

from stagelink.users.forms import OtpVerificationForm
from stagelink.users.services import OtpEmailService
from stagelink.users.services import OtpRateLimitError
from stagelink.users.services import OtpService
from stagelink.users.services import OtpVerificationError
from stagelink.users.services import OtpVerifyService
from stagelink.users.services import PasswordResetTokenService
from stagelink.utils.enums import OTPType


class VerifyOtpView(FormView):
    """
    Vérifie un code OTP pour l'inscription ou
    la réinitialisation du mot de passe.
    """

    template_name = "users/verify_otp.html"
    form_class = OtpVerificationForm

    def dispatch(self, request, *args, **kwargs):
        self.otp_type = kwargs.get("purpose")
        self.token = kwargs.get("token")

        allowed_types = {
            OTPType.SIGNUP,
            OTPType.PASSWORD_RESET,
        }

        if self.otp_type not in allowed_types:
            messages.error(
                request,
                _("Type de vérification invalide."),
            )
            return redirect("users:signin")

        if not self.token:
            messages.error(
                request,
                _("Le lien de vérification est invalide."),
            )
            return redirect("users:signin")

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )

    def get_initial(self):
        return {
            "token": self.token,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["purpose"] = self.otp_type
        context["token"] = self.token
        context["is_password_reset"] = (
            self.otp_type == OTPType.PASSWORD_RESET
    )
        return context
    
    def form_valid(self, form):
        try:
            otp = OtpVerifyService.verify(
                token=form.cleaned_data["token"],
                code=form.cleaned_data["code"],
                otp_type=self.otp_type,
            )

        except OtpVerificationError as error:
            form.add_error("code", error)
            return self.form_invalid(form)

        except ValueError as error:
            form.add_error("code", str(error))
            return self.form_invalid(form)        
        user = otp.user

        # Vérification de l'adresse e-mail
        if self.otp_type == OTPType.SIGNUP:
            user.email_verified = True
            user.save(
                update_fields=["email_verified"],
            )

            # Le token d'inscription n'est plus utile une fois l'e-mail vérifié.
            self.request.session.pop("pending_signup_token", None)

            login(
                self.request,
                user,
                backend='django.contrib.auth.backends.ModelBackend'
            )

            messages.success(
                self.request,
                _(
                    "Votre adresse e-mail a été vérifiée. "
                    "Bienvenue sur StageLink."
                ),
            )

            return redirect("users:redirect")

        # Vérification pour réinitialisation du mot de passe
        if self.otp_type == OTPType.PASSWORD_RESET:
            reset_token = PasswordResetTokenService.generate(
                user,
            )

            messages.success(
                self.request,
                _("Votre code a été vérifié."),
            )

            return redirect(
                "users:reset_password",
                token=reset_token,
            )

        messages.error(
            self.request,
            _("Type de vérification non pris en charge."),
        )

        return redirect("users:signin")

    def form_invalid(self, form):
        return super().form_invalid(form)

class ResendOtpView(View):
    """
    Génère et renvoie un nouveau code OTP.
    """

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        otp_type = kwargs.get("purpose")
        token = kwargs.get("token")

        allowed_types = {
            OTPType.SIGNUP,
            OTPType.PASSWORD_RESET,
        }

        if otp_type not in allowed_types or not token:
            messages.error(
                request,
                _("Demande de vérification invalide."),
            )
            return redirect("users:signin")

        try:
            otp = OtpVerifyService.resolve_for_resend(
            token,
            otp_type,
        )
            new_otp, new_token = OtpService.create(
                user=otp.user,
                otp_type=otp_type,
            )

            OtpEmailService.send(
                user=otp.user,
                otp=new_otp,
                language=get_language_from_request(request),
            )

        except OtpRateLimitError as error:
            messages.warning(
                request,
                error,
            )

            return redirect(
                "users:verify_otp",
                purpose=otp_type,
                token=token,
            )

        except OtpVerificationError as error:
            messages.error(
                request,
                error,
            )

            return redirect("users:signin")

        messages.success(
            request,
            _("Un nouveau code vous a été envoyé."),
        )    

        return redirect(
            "users:verify_otp",
            purpose=otp_type,
            token=new_token,
        )