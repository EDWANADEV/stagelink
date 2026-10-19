from django.urls import path

from stagelink.profiles.views import CompanyProfileView
from stagelink.profiles.views import StudentProfileView

app_name = "profiles"

urlpatterns = [
    path(
        "student/",
        StudentProfileView.as_view(),
        name="student_profile",
    ),
    path(
        "company/",
        CompanyProfileView.as_view(),
        name="company_profile",
    ),
]