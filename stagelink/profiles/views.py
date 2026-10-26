from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView
from django.views.generic import TemplateView
from django.views.generic import UpdateView

from stagelink.core.permissions import CompanyRequiredMixin
from stagelink.core.permissions import RoleRequiredMixin
from stagelink.core.permissions import StudentRequiredMixin
from stagelink.core.permissions import get_profile
from stagelink.utils.enums import Role

from .forms import CompanyProfileForm
from .forms import StudentProfileForm


class ProfileFormMixin:
    """Passe l'utilisateur connecté au formulaire de profil."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class ProfileCompleteView(RoleRequiredMixin, ProfileFormMixin, CreateView):
    """
    Création du profil, juste après la vérification de l'e-mail.
    Accessible une seule fois : si le profil existe, on part à l'espace de travail.
    """

    template_name = "profiles/profile_form.html"
    is_completion = True

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and get_profile(request.user) is not None:
            return redirect("users:redirect")

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("Votre profil est complété. Bienvenue dans votre espace StageLink !"),
        )
        return response


class ProfileUpdateView(ProfileFormMixin, UpdateView):
    template_name = "profiles/profile_form.html"
    is_completion = False
    active_nav = "profile"

    def get_object(self, queryset=None):
        # Toujours le profil de l'utilisateur connecté : aucun identifiant
        # dans l'URL, donc impossible de modifier le profil d'un autre.
        return self.profile

    def form_valid(self, form):
        messages.success(self.request, _("Votre profil a été mis à jour."))
        return super().form_valid(form)


class StudentProfileCompleteView(ProfileCompleteView):
    required_role = Role.STUDENT
    form_class = StudentProfileForm
    success_url = reverse_lazy("core:student-dashboard")


class CompanyProfileCompleteView(ProfileCompleteView):
    required_role = Role.COMPANY
    form_class = CompanyProfileForm
    success_url = reverse_lazy("core:company-dashboard")


class StudentProfileDetailView(StudentRequiredMixin, TemplateView):
    template_name = "profiles/student_detail.html"
    active_nav = "profile"

    def get_context_data(self, **kwargs):
        return super().get_context_data(profile=self.profile, **kwargs)


class CompanyProfileDetailView(CompanyRequiredMixin, TemplateView):
    template_name = "profiles/company_detail.html"
    active_nav = "profile"

    def get_context_data(self, **kwargs):
        return super().get_context_data(profile=self.profile, **kwargs)


class StudentProfileUpdateView(StudentRequiredMixin, ProfileUpdateView):
    form_class = StudentProfileForm
    success_url = reverse_lazy("profiles:student-detail")


class CompanyProfileUpdateView(CompanyRequiredMixin, ProfileUpdateView):
    form_class = CompanyProfileForm
    success_url = reverse_lazy("profiles:company-detail")


student_profile_complete_view = StudentProfileCompleteView.as_view()
company_profile_complete_view = CompanyProfileCompleteView.as_view()
student_profile_detail_view = StudentProfileDetailView.as_view()
company_profile_detail_view = CompanyProfileDetailView.as_view()
student_profile_update_view = StudentProfileUpdateView.as_view()
company_profile_update_view = CompanyProfileUpdateView.as_view()
