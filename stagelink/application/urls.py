from django.urls import path

from stagelink.application.views import ApplicationStatusView
from stagelink.application.views import ApplicationSubmitView
from stagelink.application.views import ApplicationWithdrawView
from stagelink.application.views import CompanyApplicationsView
from stagelink.application.views import StudentApplicationsView

app_name = "application"

urlpatterns = [
    path(
        "offers/<uuid:offer_pk>/apply/",
        ApplicationSubmitView.as_view(),
        name="submit",
    ),
    path("mine/", StudentApplicationsView.as_view(), name="student-list"),
    path("<uuid:pk>/withdraw/", ApplicationWithdrawView.as_view(), name="withdraw"),
    path("<uuid:pk>/status/", ApplicationStatusView.as_view(), name="change-status"),
    path("received/", CompanyApplicationsView.as_view(), name="company-list"),
]
