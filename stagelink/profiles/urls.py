from django.urls import path

from stagelink.profiles.views import DashboardView
from stagelink.profiles.views import ProfileCompletionView
from stagelink.profiles.views import StudentCVView

app_name = "profiles"

urlpatterns = [
    path(
        "complete/",
        ProfileCompletionView.as_view(),
        name="complete",
    ),
    path(
        "dashboard/",
        DashboardView.as_view(),
        name="dashboard",
    ),
    path(
        "students/<uuid:profile_pk>/cv/",
        StudentCVView.as_view(),
        name="student-cv",
    ),
]
