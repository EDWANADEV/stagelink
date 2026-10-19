from __future__ import annotations
from django.shortcuts import render

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from stagelink.profiles.forms import CompanyProfileForm
from stagelink.profiles.forms import StudentProfileForm
from stagelink.profiles.models import CompanyProfile
from stagelink.profiles.models import StudentProfile
from stagelink.utils.enums import Role


class ProfileAccessMixin(LoginRequiredMixin):
    """Contrôle l'accès au profil selon le rôle de l'utilisateur."""

    login_url = "users:signin"
    role = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.role != self.role:
            return redirect("users:redirect")

        return super().dispatch(request, *args, **kwargs)


class StudentProfileView(ProfileAccessMixin, FormView):
    """Permet à un étudiant de créer ou modifier son profil."""

    template_name = "profiles/student_form.html"
    form_class = StudentProfileForm
    role = Role.STUDENT

    def get_profile(self):
        """Récupère le profil de l'étudiant connecté, s'il existe."""
        return StudentProfile.objects.filter(
            user=self.request.user
        ).first()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_profile()
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.user = self.request.user
            form.save()

        messages.success(
            self.request,
            _("Votre profil étudiant a été enregistré avec succès."),
        )
        return redirect("profiles:student_profile")

    def form_invalid(self, form):
        messages.error(
            self.request,
            _("Veuillez corriger les erreurs du formulaire."),
        )
        return super().form_invalid(form)


class CompanyProfileView(ProfileAccessMixin, FormView):
    """Permet à une entreprise de créer ou modifier son profil."""

    template_name = "profiles/company_form.html"
    form_class = CompanyProfileForm
    role = Role.COMPANY

    def get_profile(self):
        """Récupère le profil de l'entreprise connectée, s'il existe."""
        return CompanyProfile.objects.filter(
            user=self.request.user
        ).first()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_profile()
        return kwargs

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.user = self.request.user
            form.save()

        messages.success(
            self.request,
            _("Votre profil entreprise a été enregistré avec succès."),
        )
        return redirect("profiles:company_profile")

    def form_invalid(self, form):
        messages.error(
            self.request,
            _("Veuillez corriger les erreurs du formulaire."),
        )
        return super().form_invalid(form)
    
