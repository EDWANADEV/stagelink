from django.urls import path

from .views import DonationPageView

app_name = "donation"

urlpatterns = [
    path("", DonationPageView.as_view(), name="donate"),
]
