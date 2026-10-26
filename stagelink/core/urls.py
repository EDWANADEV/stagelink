from django.urls import path

from .views import company_dashboard_view
from .views import student_dashboard_view

app_name = "core"
urlpatterns = [
    path("student/", view=student_dashboard_view, name="student-dashboard"),
    path("company/", view=company_dashboard_view, name="company-dashboard"),
]
