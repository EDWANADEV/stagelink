import json
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from djmoney.money import Money

from stagelink.donation.models import Donation
from stagelink.donation.services import DonationService
from stagelink.utils.enums import DonationStatus
from stagelink.utils.enums import PaymentMethod
from stagelink.utils.enums import PaymentProvider
from stagelink.utils.enums import PaymentStatus

from .models import Payment
from .models import WebhookEvent
from .services import PaymentService
from .tasks import _process_provider_event
from .tasks import process_webhook_event


@override_settings(
    STRIPE_PUBLISHABLE_KEY="pk_test_fake",
    STRIPE_WEBHOOK_SECRET="whsec_test_fake",
)
class PaymentFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="donor@example.com",
            password="test-password",
        )
        self.donation = DonationService.create_donation(
            donor=self.user,
            amount=Money(5000, "XAF"),
        )

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_fake",
        STRIPE_WEBHOOK_SECRET="whsec_test_fake",
    )
    def test_payment_creation_and_idempotency(self):
        first = PaymentService.create_payment(
            donation=self.donation,
            method=PaymentMethod.CARD,
            provider=PaymentProvider.STRIPE,
            idempotency_key="request-1",
        )
        second = PaymentService.create_payment(
            donation=self.donation,
            method=PaymentMethod.CARD,
            provider=PaymentProvider.STRIPE,
            idempotency_key="request-1",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Payment.objects.count(), 1)

    @override_settings(STRIPE_ENABLED=False, STRIPE_SECRET_KEY="sk_test_fake")
    def test_disabled_provider_is_rejected(self):
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                donation=self.donation,
                method=PaymentMethod.CARD,
                provider=PaymentProvider.STRIPE,
            )

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_SECRET_KEY="",
        STRIPE_WEBHOOK_SECRET="whsec_test_fake",
    )
    def test_missing_provider_credentials_are_rejected(self):
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                donation=self.donation,
                method=PaymentMethod.CARD,
                provider=PaymentProvider.STRIPE,
            )

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_fake",
        STRIPE_WEBHOOK_SECRET="whsec_test_fake",
    )
    def test_options_only_show_enabled_configured_provider(self):
        response = self.client.get(reverse("payments:options"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["payment_methods"],
            [
                {"provider": "stripe", "method": "card"},
            ],
        )

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_fake",
        STRIPE_WEBHOOK_SECRET="whsec_test_fake",
    )
    def test_create_endpoint_idempotency_key_reuses_payment(self):
        payload = {"amount": "5000", "provider": "stripe", "method": "card"}
        with (
            patch(
                "stagelink.payments.views.StripeService.create_payment_intent",
            ) as create,
            patch(
                "stagelink.payments.views.StripeService.retrieve_payment_intent",
            ) as retrieve,
        ):
            create.return_value = {
                "id": "pi_test",
                "client_secret": "secret",
                "response": {},
            }
            retrieve.return_value.client_secret = "secret"
            first = self.client.post(
                reverse("payments:create"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY="request-api-1",
            )
            second = self.client.post(
                reverse("payments:create"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY="request-api-1",
            )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Donation.objects.count(), 2)
        self.assertEqual(Payment.objects.count(), 1)

    @override_settings(STRIPE_ENABLED=False, FLUTTERWAVE_ENABLED=False)
    def test_no_enabled_provider_creates_no_donation_or_payment(self):
        response = self.client.post(
            reverse("payments:create"),
            data=json.dumps(
                {"amount": "5000", "provider": "stripe", "method": "card"},
            ),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="no-provider-request",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Donation.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 0)

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_fake",
        STRIPE_WEBHOOK_SECRET="whsec_fake",
    )
    def test_signed_webhook_is_durably_recorded_and_duplicate_is_ignored(self):
        event = {
            "id": "evt-1",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {"id": "pi_1", "metadata": {"stagelink_payment_id": "x"}},
            },
        }
        with (
            patch(
                "stagelink.payments.webhooks.stripe.Webhook.construct_event",
                return_value=event,
            ),
            patch("stagelink.payments.webhooks.process_webhook_event.delay") as enqueue,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(
                reverse("payments:stripe-webhook"),
                data=b"{}",
                content_type="application/json",
            )
            duplicate = self.client.post(
                reverse("payments:stripe-webhook"),
                data=b"{}",
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(
            WebhookEvent.objects.filter(provider="stripe", event_id="evt-1").count(),
            1,
        )
        enqueue.assert_called_once()

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_fake")
    def test_invalid_signature_is_rejected(self):
        with patch(
            "stagelink.payments.webhooks.stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError("invalid", "bad"),
        ):
            response = self.client.post(
                reverse("payments:stripe-webhook"),
                data=b"{}",
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    @override_settings(FLW_WEBHOOK_SECRET="hook-secret")
    def test_flutterwave_bad_signature_rejected_and_providers_isolated(self):
        response = self.client.post(
            reverse("payments:flutterwave-webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_VERIF_HASH="wrong",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    @override_settings(FLW_WEBHOOK_SECRET="hook-secret")
    def test_valid_flutterwave_event_is_recorded_once(self):
        body = {
            "id": "flw-event-1",
            "event": "charge.completed",
            "data": {"id": 123, "tx_ref": "payment-ref"},
        }
        with (
            patch("stagelink.payments.webhooks.process_webhook_event.delay") as enqueue,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(
                reverse("payments:flutterwave-webhook"),
                data=json.dumps(body),
                content_type="application/json",
                HTTP_VERIF_HASH="hook-secret",
            )
            duplicate = self.client.post(
                reverse("payments:flutterwave-webhook"),
                data=json.dumps(body),
                content_type="application/json",
                HTTP_VERIF_HASH="hook-secret",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(
            WebhookEvent.objects.filter(provider="flutterwave").count(),
            1,
        )
        enqueue.assert_called_once()

    def test_success_marks_payment_and_donation_together(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        PaymentService.mark_as_success(payment=payment, provider_payment_id="pi_ok")
        self.donation.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCESS)
        self.assertEqual(self.donation.status, DonationStatus.COMPLETED)

    def test_verified_stripe_success_marks_payment_and_donation(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        event = WebhookEvent(
            provider="stripe",
            event_id="evt-success",
            event_type="payment_intent.succeeded",
            payload={
                "id": "evt-success",
                "data": {
                    "object": {
                        "id": "pi_success",
                        "metadata": {"stagelink_payment_id": str(payment.pk)},
                    },
                },
            },
        )
        with patch(
            "stagelink.payments.tasks.StripeService.retrieve_payment_intent",
            return_value={
                "metadata": {"stagelink_payment_id": str(payment.pk)},
                "currency": "xaf",
                "amount": 5000,
                "status": "succeeded",
            },
        ):
            _process_provider_event(event)
        payment.refresh_from_db()
        self.donation.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCESS)
        self.assertEqual(self.donation.status, DonationStatus.COMPLETED)

    def test_flutterwave_amount_and_currency_are_checked(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.FLUTTERWAVE,
            method=PaymentMethod.MOBILE_MONEY,
        )
        event = WebhookEvent(
            provider="flutterwave",
            event_id="flw-check",
            event_type="charge.completed",
            payload={
                "data": {"id": 44, "tx_ref": str(payment.pk)},
            },
        )
        wrong_values = [
            {"id": 44, "tx_ref": str(payment.pk), "currency": "XAF", "amount": 1},
            {"id": 44, "tx_ref": str(payment.pk), "currency": "USD", "amount": 5000},
        ]
        for verified in wrong_values:
            with (
                self.subTest(verified=verified),
                patch(
                    "stagelink.payments.tasks.FlutterwaveService.verify_transaction",
                    return_value=verified,
                ),
                self.assertRaises(ValueError),
            ):
                _process_provider_event(event)

    def test_failure_marks_donation_failed(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        PaymentService.mark_as_failed(payment=payment, failure_reason="declined")
        self.donation.refresh_from_db()
        self.assertEqual(self.donation.status, DonationStatus.FAILED)

    def test_cancelled_payment_marks_donation_cancelled(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        PaymentService.mark_as_cancelled(payment=payment)
        self.donation.refresh_from_db()
        self.assertEqual(self.donation.status, DonationStatus.CANCELLED)

    def test_rollback_keeps_payment_and_donation_consistent(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        with patch(
            "stagelink.payments.services.Payment.save",
            side_effect=RuntimeError("db error"),
        ):
            with self.assertRaises(RuntimeError):
                PaymentService.mark_as_success(
                    payment=payment,
                    provider_payment_id="pi_rollback",
                )
        self.donation.refresh_from_db()
        self.assertEqual(self.donation.status, DonationStatus.PENDING)

    def test_event_processing_is_idempotent(self):
        event = WebhookEvent.objects.create(
            provider="stripe",
            event_id="evt-done",
            event_type="ignored",
            payload={},
            status=WebhookEvent.Status.PROCESSED,
        )
        process_webhook_event.run(str(event.pk))
        event.refresh_from_db()
        self.assertEqual(event.attempts, 0)

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_fake",
        STRIPE_WEBHOOK_SECRET="whsec_test_fake",
    )
    def test_failed_event_is_retryable(self):
        event = WebhookEvent.objects.create(
            provider="stripe",
            event_id="evt-retry",
            event_type="ignored",
            payload={},
        )
        with patch(
            "stagelink.payments.tasks._process_provider_event",
            side_effect=RuntimeError("temporary"),
        ):
            with self.assertRaises(Exception):
                process_webhook_event.run(str(event.pk))
        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.Status.RECEIVED)
        self.assertIn("temporary", event.last_error)
