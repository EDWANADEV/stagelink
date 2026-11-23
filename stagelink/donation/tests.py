from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from djmoney.money import Money

from stagelink.donation.forms import DonationForm
from stagelink.donation.services import DonationService
from stagelink.payments.models import Payment
from stagelink.utils.enums import PaymentMethod
from stagelink.utils.enums import PaymentProvider
from stagelink.utils.enums import PaymentStatus


class DonationPageTests(TestCase):
    def test_donation_page_is_reachable_and_explains_its_purpose(self):
        with self.settings(
            STRIPE_ENABLED=True,
            STRIPE_PUBLISHABLE_KEY="pk_test_example",
            STRIPE_SECRET_KEY="sk_test_example",
            STRIPE_WEBHOOK_SECRET="whsec_example",
        ):
            response = self.client.get(reverse("donation:donate"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Soutenez les opportunités de stage")

    @override_settings(
        STRIPE_ENABLED=False,
        FLUTTERWAVE_ENABLED=False,
    )
    def test_no_payment_provider_shows_explanation_and_no_payment_form(self):
        response = self.client.get(reverse("donation:donate"))

        self.assertContains(response, "Les paiements sont temporairement indisponibles")
        self.assertNotContains(response, 'id="donation-form"')
        self.assertNotContains(response, "Stripe")
        self.assertNotContains(response, "Flutterwave")

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_PUBLISHABLE_KEY="pk_test_example",
        STRIPE_SECRET_KEY="sk_test_example",
        STRIPE_WEBHOOK_SECRET="whsec_example",
        FLUTTERWAVE_ENABLED=False,
    )
    def test_only_enabled_configured_stripe_method_is_rendered(self):
        response = self.client.get(reverse("donation:donate"))

        self.assertContains(response, "Carte bancaire via Stripe")
        self.assertNotContains(response, "Mobile Money via Flutterwave")
        self.assertNotContains(response, "Carte bancaire via Flutterwave")

    @override_settings(
        STRIPE_ENABLED=False,
        FLUTTERWAVE_ENABLED=True,
        FLW_SECRET_KEY="FLWSECK_TEST-example",
        FLW_WEBHOOK_SECRET="webhook-hash-example",
    )
    def test_only_configured_flutterwave_methods_are_rendered(self):
        response = self.client.get(reverse("donation:donate"))

        self.assertContains(response, "Mobile Money via Flutterwave")
        self.assertContains(response, "Carte bancaire via Flutterwave")
        self.assertNotContains(response, "Carte bancaire via Stripe")

    def test_donation_amount_rules_and_presets(self):
        self.assertTrue(DonationForm(data={"amount": "5000"}).is_valid())
        self.assertFalse(DonationForm(data={"amount": "0"}).is_valid())
        self.assertFalse(DonationForm(data={"amount": "12.5"}).is_valid())
        self.assertFalse(DonationForm(data={"amount": "10000000000"}).is_valid())
        with self.settings(
            STRIPE_ENABLED=True,
            STRIPE_PUBLISHABLE_KEY="pk_test_example",
            STRIPE_SECRET_KEY="sk_test_example",
            STRIPE_WEBHOOK_SECRET="whsec_example",
        ):
            response = self.client.get(reverse("donation:donate"))
        self.assertContains(response, 'data-amount="1000"')
        self.assertContains(response, 'data-amount="5000"')
        self.assertContains(response, 'data-amount="10000"')

    def test_return_page_displays_each_provider_persisted_state(self):
        donation = DonationService.create_donation(amount=Money(5000, "XAF"))
        payment = Payment.objects.create(
            donation=donation,
            amount=donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        expected = {
            PaymentStatus.PENDING: "Paiement en attente",
            PaymentStatus.SUCCESS: "Paiement confirmé",
            PaymentStatus.FAILED: "Paiement échoué",
            PaymentStatus.CANCELLED: "Paiement annulé",
            PaymentStatus.REFUNDED: "Paiement remboursé",
            PaymentStatus.PARTIALLY_REFUNDED: "Paiement partiellement remboursé",
        }
        for status, label in expected.items():
            payment.status = status
            payment.save(update_fields=["status"])
            response = self.client.get(
                reverse("payments:return"),
                {"payment_id": payment.pk},
            )
            self.assertContains(response, label)

    def test_browser_return_cannot_confirm_a_payment(self):
        donation = DonationService.create_donation(amount=Money(5000, "XAF"))
        payment = Payment.objects.create(
            donation=donation,
            amount=donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )

        response = self.client.get(
            reverse("payments:return"),
            {"payment_id": payment.pk, "status": "success"},
        )

        payment.refresh_from_db()
        self.assertContains(response, "Paiement en attente")
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_cancel_return_notice_does_not_change_or_assert_payment_state(self):
        donation = DonationService.create_donation(amount=Money(5000, "XAF"))
        payment = Payment.objects.create(
            donation=donation,
            amount=donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )

        response = self.client.get(
            reverse("payments:return"),
            {"payment_id": payment.pk, "cancelled": "1"},
        )

        self.assertContains(response, "Cela ne confirme ni n’annule le paiement")
        self.assertContains(response, "Paiement en attente")
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.PENDING)
