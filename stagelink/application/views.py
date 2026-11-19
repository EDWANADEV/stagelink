from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import FormView
from django.views.generic import ListView

from stagelink.application.forms import ApplicationStatusForm
from stagelink.application.forms import ApplicationSubmissionForm
from stagelink.application.forms import ApplicationWithdrawalForm
from stagelink.application.services import ApplicationService
from stagelink.offers.models import InternshipOffer
from stagelink.profiles.services import get_profile
from stagelink.profiles.services import is_profile_complete
from stagelink.utils.enums import ApplicationMode
from stagelink.utils.enums import Role

from .models import Application


class ApplicationRoleMixin(LoginRequiredMixin):
    login_url = "users:signin"
    role = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.email_verified:
            return redirect("users:signin")
        if request.user.role != self.role:
            raise PermissionDenied

        self.profile = getattr(request, "stagelink_profile", None)
        if self.profile is None:
            self.profile = get_profile(request.user)
        if self.profile is None or not is_profile_complete(
            request.user,
            self.profile,
        ):
            return redirect("profiles:complete")

        return super().dispatch(request, *args, **kwargs)


class StudentApplicationsView(ApplicationRoleMixin, ListView):
    """Liste uniquement les candidatures de l'étudiant connecté."""

    role = Role.STUDENT
    template_name = "application/student_list.html"
    context_object_name = "applications"
    paginate_by = 20

    def get_queryset(self):
        return (
            Application.objects.filter(student=self.profile)
            .select_related("offer", "offer__company")
            .prefetch_related("status_history__changed_by")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for application in context["applications"]:
            application.withdraw_form = ApplicationWithdrawalForm(
                application=application,
            )
        return context


class CompanyApplicationsView(ApplicationRoleMixin, ListView):
    """Candidatures reçues pour les offres créées par l'entreprise."""

    role = Role.COMPANY
    template_name = "application/company_list.html"
    context_object_name = "applications"
    paginate_by = 20

    def get_queryset(self):
        return (
            Application.objects.filter(
                offer__company=self.profile,
                offer__created_by=self.request.user,
            )
            .select_related(
                "student",
                "student__user",
                "offer",
            )
            .prefetch_related("status_history__changed_by")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for application in context["applications"]:
            application.status_form = ApplicationStatusForm(
                application=application,
            )
        return context


class ApplicationSubmitView(ApplicationRoleMixin, FormView):
    role = Role.STUDENT
    template_name = "application/submit.html"
    form_class = ApplicationSubmissionForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["student_profile"] = self.profile
        return kwargs

    def get_offer(self):
        if not hasattr(self, "offer"):
            self.offer = get_object_or_404(
                InternshipOffer.objects.available().select_related("company"),
                pk=self.kwargs["offer_pk"],
                application_mode=ApplicationMode.INTERNAL,
                company__isnull=False,
            )
        return self.offer

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["offer"] = self.get_offer()
        return context

    def form_valid(self, form):
        try:
            ApplicationService.submit(
                student=self.profile,
                offer=self.get_offer(),
                cover_letter=form.cleaned_data["cover_letter"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)

        messages.success(self.request, _("Votre candidature a été envoyée."))
        return redirect("application:student-list")


class ApplicationWithdrawView(ApplicationRoleMixin, View):
    role = Role.STUDENT
    http_method_names = ["post"]

    def post(self, request, pk):
        application = get_object_or_404(
            Application.objects.select_related("student__user", "offer__company"),
            pk=pk,
            student=self.profile,
        )
        form = ApplicationWithdrawalForm(
            request.POST,
            application=application,
        )
        if not form.is_valid():
            messages.error(request, _("Un motif de retrait est requis."))
            return redirect("application:student-list")

        try:
            ApplicationService.withdraw(
                application=application,
                student=self.profile,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, _("Votre candidature a été retirée."))
        return redirect("application:student-list")


class ApplicationStatusView(ApplicationRoleMixin, View):
    role = Role.COMPANY
    http_method_names = ["post"]

    def post(self, request, pk):
        application = get_object_or_404(
            Application.objects.select_related(
                "student__user",
                "offer__company",
            ),
            pk=pk,
            offer__company=self.profile,
            offer__created_by=request.user,
        )
        form = ApplicationStatusForm(request.POST, application=application)
        if not form.is_valid():
            messages.error(
                request,
                _("Vérifiez le nouveau statut et la date d'entretien."),
            )
            return redirect("application:company-list")

        try:
            ApplicationService.change_status(
                application=application,
                new_status=form.cleaned_data["status"],
                updated_by=request.user,
                interview_at=form.cleaned_data["interview_at"],
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(
                request,
                _("Le statut de la candidature a été mis à jour."),
            )
        return redirect("application:company-list")
