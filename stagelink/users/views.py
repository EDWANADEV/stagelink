from __future__ import annotations

from typing import TYPE_CHECKING

from .forms import LoginForm
from .forms import SignupForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth import login
from django.urls import reverse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import FormView
from django.views.generic import UpdateView
from django.contrib.auth import login
from django.shortcuts import redirect

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



class SignupView(FormView):
    template_name = "users/signup.html"
    form_class = SignupForm

    def form_valid(self, form):
        user = User.objects.create_user(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
            name=form.cleaned_data["name"],
            role=form.cleaned_data["role"],
            is_active=False,
        )

        self.request.session["pending_signup_user_id"] = user.pk

        messages.success(
            self.request,
            _("Votre compte a été créé. Un code de vérification vous sera envoyé."),
        )

        return redirect("users:verify-otp")


signup_view = SignupView.as_view()