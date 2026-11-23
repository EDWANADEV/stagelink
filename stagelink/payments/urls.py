from django.urls import path

from . import views
from . import webhooks

app_name = "payments"

urlpatterns = [
    path("options/", views.payment_options, name="options"),
    path("create/", views.create_payment, name="create"),
    path("return/", views.payment_return, name="return"),
    path(
        "return/<uuid:payment_id>/status/",
        views.payment_return_status,
        name="return-status",
    ),
    path("webhooks/stripe/", webhooks.stripe_webhook, name="stripe-webhook"),
    path(
        "webhooks/flutterwave/",
        webhooks.flutterwave_webhook,
        name="flutterwave-webhook",
    ),
]
