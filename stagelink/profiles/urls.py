from django.urls import path

from .views import company_profile_complete_view
from .views import company_profile_detail_view
from .views import company_profile_update_view
from .views import student_profile_complete_view
from .views import student_profile_detail_view
from .views import student_profile_update_view

app_name = "profiles"
urlpatterns = [
    path("student/", view=student_profile_detail_view, name="student-detail"),
    path(
        "student/complete/",
        view=student_profile_complete_view,
        name="student-complete",
    ),
    path("student/edit/", view=student_profile_update_view, name="student-edit"),
    path("company/", view=company_profile_detail_view, name="company-detail"),
    path(
        "company/complete/",
        view=company_profile_complete_view,
        name="company-complete",
    ),
    path("company/edit/", view=company_profile_update_view, name="company-edit"),
]
