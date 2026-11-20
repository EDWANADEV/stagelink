from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from stagelink.payments.services import get_available_payment_methods


class DonationPageView(TemplateView):
    template_name = "donation/donate.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        options = []
        labels = {
            ("stripe", "card"): _("Carte bancaire via Stripe"),
            ("flutterwave", "card"): _("Carte bancaire via Flutterwave"),
            ("flutterwave", "mobile_money"): _("Mobile Money via Flutterwave"),
        }
        for provider, method in get_available_payment_methods():
            options.append(
                {
                    "provider": provider,
                    "method": method,
                    "value": f"{provider}:{method}",
                    "label": labels[(provider, method)],
                },
            )
        context["payment_methods"] = options
        context["stripe_available"] = any(
            option["provider"] == "stripe" for option in options
        )
        context["stripe_publishable_key"] = settings.STRIPE_PUBLISHABLE_KEY
        context["donor_email"] = (
            self.request.user.email if self.request.user.is_authenticated else ""
        )
        context["preset_amounts"] = (1000, 5000, 10000)
        return context
