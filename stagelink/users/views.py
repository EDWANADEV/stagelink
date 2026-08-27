from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView
from django.views.generic import FormView
from django.views.generic import RedirectView
from django.views.generic import UpdateView

from stagelink.users.forms import OTPVerificationForm
from stagelink.users.models import OTPVerification
from stagelink.users.services.otp import OTPService

from .forms import LoginForm
from .forms import UserSignupForm
from .models import User

if TYPE_CHECKING:
    from django.db.models import QuerySet


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"


user_detail_view = UserDetailView.as_view()


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None = None) -> User:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user


user_update_view = UserUpdateView.as_view()


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self) -> str:
        return reverse("users:detail", kwargs={"pk": self.request.user.pk})


user_redirect_view = UserRedirectView.as_view()


class LoginView(FormView):
    template_name = "users/login.html"
    form_class = LoginForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        user = form.get_user()

        login(self.request, user)

        return redirect("users:redirect")


login_view = LoginView.as_view()


class SignupView(View):
    template_name = "users/signup.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("users:redirect")

        form = UserSignupForm()

        return render(
            request,
            self.template_name,
            {"form": form},
        )

    def post(self, request):
        if request.user.is_authenticated:
            return redirect("users:redirect")

        form = UserSignupForm(request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"form": form},
            )

        user = User.objects.create_user(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
            role=form.cleaned_data["role"],
        )

        login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )

        OTPService.send_otp(
            user=user,
            otp_type=OTPVerification.OTPType.SIGNUP,
        )

        messages.success(
            request,
            _(
                "Votre compte a été créé."
                "Un code de vérification vous a été envoyé par e-mail.",
            ),
        )

        return redirect("users:verify-email")


signup_view = SignupView.as_view()


class VerifyEmailView(LoginRequiredMixin, FormView):
    template_name = "users/verify_otp.html"
    form_class = OTPVerificationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.email_verified:
            return redirect("users:redirect")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        success, message = OTPService.verify_otp(
            user=self.request.user,
            code=form.cleaned_data["code"],
            otp_type=OTPVerification.OTPType.SIGNUP,
        )

        if not success:
            form.add_error("code", message)
            return self.form_invalid(form)

        self.request.user.email_verified = True
        self.request.user.save(update_fields=["email_verified"])

        messages.success(
            self.request,
            _("Votre adresse e-mail a été vérifiée avec succès."),
        )

        return redirect("users:redirect")


verify_email_view = VerifyEmailView.as_view()


class LogoutView(View):
    def post(self, request):
        logout(request)

        messages.success(
            request,
            _("Vous avez été déconnecté avec succès."),
        )

        return redirect("home")


logout_view = LogoutView.as_view()
