from django.views.generic import TemplateView

from stagelink.application.models import Application
from stagelink.notifications.models import Notification
from stagelink.offers.models import InternshipOffer
from stagelink.utils.enums import OfferStatus

from .permissions import CompanyRequiredMixin
from .permissions import StudentRequiredMixin

RECENT_ITEMS_LIMIT = 5


class StudentDashboardView(StudentRequiredMixin, TemplateView):
    template_name = "dashboard/student.html"
    active_nav = "dashboard"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applications = Application.objects.filter(student=self.profile)

        context.update(
            profile=self.profile,
            applications_count=applications.count(),
            recent_applications=applications.select_related(
                "offer",
                "offer__company",
            )[:RECENT_ITEMS_LIMIT],
            available_offers_count=InternshipOffer.objects.available().count(),
            unread_notifications_count=Notification.objects.filter(
                user=self.request.user,
                is_read=False,
            ).count(),
        )
        return context


class CompanyDashboardView(CompanyRequiredMixin, TemplateView):
    template_name = "dashboard/company.html"
    active_nav = "dashboard"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        offers = InternshipOffer.objects.filter(company=self.profile)
        applications = Application.objects.filter(offer__company=self.profile)

        context.update(
            profile=self.profile,
            published_offers_count=offers.filter(
                status=OfferStatus.PUBLISHED,
            ).count(),
            draft_offers_count=offers.filter(status=OfferStatus.DRAFT).count(),
            applications_count=applications.count(),
            recent_applications=applications.select_related(
                "offer",
                "student__user",
            )[:RECENT_ITEMS_LIMIT],
            unread_notifications_count=Notification.objects.filter(
                user=self.request.user,
                is_read=False,
            ).count(),
        )
        return context


student_dashboard_view = StudentDashboardView.as_view()
company_dashboard_view = CompanyDashboardView.as_view()
