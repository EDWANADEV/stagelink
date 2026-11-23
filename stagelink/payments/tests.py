import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from http import HTTPStatus
from threading import Event
from unittest.mock import Mock
from unittest.mock import patch

import pytest
import stripe
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.db import connection
from django.db import close_old_connections
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from djmoney.money import Money

from stagelink.donation.models import Donation
from stagelink.donation.services import DonationService
from stagelink.utils.enums import DonationStatus
from stagelink.utils.enums import PaymentMethod
from stagelink.utils.enums import PaymentProvider
from stagelink.utils.enums import PaymentStatus

from .models import Payment
from .models import WebhookEvent
from .providers.stripe import StripeService
from .services import PaymentService
from .tasks import PROCESSING_LEASE
from .tasks import _process_provider_event
from .tasks import process_webhook_event
from .tasks import reprocess_failed_webhook_events


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

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_fake",
        STRIPE_PUBLISHABLE_KEY="pk_test_fake",
        STRIPE_WEBHOOK_SECRET="whsec_test_fake",
    )
    def test_stripe_adapter_serializes_with_supported_sdk_api(self):
        intent = Mock()
        intent.id = "pi_test"
        intent.client_secret = "test_client_secret"
        intent.to_dict.return_value = {
            "id": "pi_test",
            "client_secret": "test_client_secret",
            "currency": "xaf",
            "amount": 5000,
        }
        with patch(
            "stagelink.payments.providers.stripe.stripe.PaymentIntent.create",
            return_value=intent,
        ) as create:
            result = StripeService.create_payment_intent(payment=Payment(
                donation=self.donation,
                amount=self.donation.amount,
                provider=PaymentProvider.STRIPE,
                method=PaymentMethod.CARD,
            ))

        self.assertEqual(result["id"], "pi_test")
        self.assertEqual(result["client_secret"], "test_client_secret")
        self.assertNotIn("client_secret", result["response"])
        self.assertEqual(result["response"]["currency"], "xaf")
        self.assertEqual(create.call_args.kwargs["amount"], 5000)

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_fake",
        STRIPE_PUBLISHABLE_KEY="pk_test_fake",
        STRIPE_WEBHOOK_SECRET="whsec_test_fake",
    )
    def test_stripe_checkout_session_uses_xaf_and_secure_return_urls(self):
        session = Mock()
        session.id = "cs_test"
        session.url = "https://checkout.stripe.com/c/pay/test"
        session.to_dict.return_value = {"id": "cs_test", "status": "open"}
        payment = Payment(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        with patch(
            "stagelink.payments.providers.stripe.stripe.checkout.Session.create",
            return_value=session,
        ) as create:
            result = StripeService.create_checkout_session(
                payment=payment,
                success_url=(
                    "http://localhost:8000/payments/return/?payment_id=x"
                    "&checkout_session_id={CHECKOUT_SESSION_ID}"
                ),
                cancel_url="http://localhost:8000/payments/return/?payment_id=x&cancelled=1",
            )

        self.assertEqual(result["url"], session.url)
        params = create.call_args.kwargs
        self.assertEqual(params["mode"], "payment")
        self.assertEqual(params["line_items"][0]["price_data"]["currency"], "xaf")
        self.assertEqual(params["line_items"][0]["price_data"]["unit_amount"], 5000)
        self.assertIn("{CHECKOUT_SESSION_ID}", params["success_url"])
        self.assertTrue(params["cancel_url"].startswith("http://localhost:8000/"))
        self.assertEqual(params["idempotency_key"], f"payment:{payment.pk}")

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_fake",
        STRIPE_WEBHOOK_SECRET="whsec_test_fake",
    )
    def test_stripe_timeout_returns_generic_gateway_error_and_safe_log(self):
        payload = {"amount": "5000", "provider": "stripe", "method": "card"}
        with (
            patch(
                "stagelink.payments.views.StripeService.create_checkout_session",
                side_effect=stripe.APIConnectionError("timeout"),
            ),
            self.assertLogs("stagelink.payments.views", level="ERROR") as logs,
        ):
            response = self.client.post(
                reverse("payments:create"),
                data=json.dumps(payload),
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY="stripe-timeout-request",
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {"error": "Le prestataire de paiement est indisponible."},
        )
        self.assertIn("exception_type=APIConnectionError", logs.output[0])

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
                "stagelink.payments.views.StripeService.create_checkout_session",
            ) as create,
            patch(
                "stagelink.payments.views.StripeService.retrieve_checkout_session",
            ) as retrieve,
        ):
            create.return_value = {
                "id": "cs_test",
                "url": "https://checkout.stripe.com/c/pay/test",
                "response": {"status": "open"},
            }
            retrieve.return_value.status = "open"
            retrieve.return_value.url = "https://checkout.stripe.com/c/pay/test"
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
        self.assertTrue(
            first.json()["checkout_url"].startswith("https://checkout.stripe.com/"),
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["checkout_url"], second.json()["checkout_url"])
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
            patch("stagelink.payments.tasks.process_webhook_event.delay") as enqueue,
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

    @override_settings(
        STRIPE_ENABLED=True,
        STRIPE_SECRET_KEY="sk_test_fake",
        STRIPE_WEBHOOK_SECRET="whsec_fake",
    )
    def test_duplicate_delivery_retries_after_publication_failure(self):
        event = {
            "id": "evt-publish-retry",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test", "metadata": {}}},
        }
        with (
            patch(
                "stagelink.payments.webhooks.stripe.Webhook.construct_event",
                return_value=event,
            ),
            patch(
                "stagelink.payments.tasks.process_webhook_event.delay",
                side_effect=[RuntimeError("redis unavailable"), Mock()],
            ) as enqueue,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.client.post(
                reverse("payments:stripe-webhook"),
                data=b"{}",
                content_type="application/json",
            )
            self.client.post(
                reverse("payments:stripe-webhook"),
                data=b"{}",
                content_type="application/json",
            )
        self.assertEqual(enqueue.call_count, 2)
        stored = WebhookEvent.objects.get(event_id="evt-publish-retry")
        self.assertEqual(stored.status, WebhookEvent.Status.RECEIVED)
        self.assertIsNotNone(stored.last_dispatched_at)

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
            patch("stagelink.payments.tasks.process_webhook_event.delay") as enqueue,
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
                "id": "pi_success",
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

    def test_verified_checkout_completion_marks_payment_and_donation(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        event = WebhookEvent(
            provider="stripe",
            event_id="evt-checkout-complete",
            event_type="checkout.session.completed",
            payload={
                "id": "evt-checkout-complete",
                "data": {
                    "object": {
                        "id": "cs_test",
                        "metadata": {"stagelink_payment_id": str(payment.pk)},
                    },
                },
            },
        )
        verified_session = {
            "id": "cs_test",
            "metadata": {"stagelink_payment_id": str(payment.pk)},
            "currency": "xaf",
            "amount_total": 5000,
            "status": "complete",
            "payment_status": "paid",
            "payment_intent": "pi_test",
        }
        verified_intent = {
            "id": "pi_test",
            "metadata": {"stagelink_payment_id": str(payment.pk)},
            "currency": "xaf",
            "amount": 5000,
            "status": "succeeded",
        }
        with (
            patch(
                "stagelink.payments.tasks.StripeService.retrieve_checkout_session",
                return_value=verified_session,
            ),
            patch(
                "stagelink.payments.tasks.StripeService.retrieve_payment_intent",
                return_value=verified_intent,
            ),
        ):
            _process_provider_event(event)

        payment.refresh_from_db()
        self.donation.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCESS)
        self.assertEqual(payment.provider_payment_id, "pi_test")
        self.assertEqual(self.donation.status, DonationStatus.COMPLETED)

    def test_expired_checkout_session_cancels_pending_donation(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        event = WebhookEvent(
            provider="stripe",
            event_id="evt-checkout-expired",
            event_type="checkout.session.expired",
            payload={
                "id": "evt-checkout-expired",
                "data": {
                    "object": {
                        "id": "cs_expired",
                        "metadata": {"stagelink_payment_id": str(payment.pk)},
                    },
                },
            },
        )
        verified_session = {
            "id": "cs_expired",
            "metadata": {"stagelink_payment_id": str(payment.pk)},
            "currency": "xaf",
            "amount_total": 5000,
            "status": "expired",
        }
        with patch(
            "stagelink.payments.tasks.StripeService.retrieve_checkout_session",
            return_value=verified_session,
        ):
            _process_provider_event(event)

        payment.refresh_from_db()
        self.donation.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.CANCELLED)
        self.assertEqual(self.donation.status, DonationStatus.CANCELLED)

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
            event_type="unknown.event",
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
            event_type="unknown.event",
            payload={},
        )
        with patch(
            "stagelink.payments.tasks._process_provider_event",
            side_effect=RuntimeError("temporary"),
        ):
            process_webhook_event.run(str(event.pk))
        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.Status.RECEIVED)
        self.assertEqual(event.last_error, "RuntimeError")

    def test_unsupported_stripe_event_is_ignored(self):
        event = WebhookEvent.objects.create(
            provider="stripe",
            event_id="evt-ignored",
            event_type="charge.succeeded",
            payload={},
        )
        process_webhook_event.run(str(event.pk))
        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.Status.IGNORED)

    def test_missing_payment_reference_is_terminal_invalid(self):
        event = WebhookEvent.objects.create(
            provider="stripe",
            event_id="evt-no-ref",
            event_type="payment_intent.succeeded",
            payload={"id": "evt-no-ref", "data": {"object": {"id": "pi_no_ref"}}},
        )
        process_webhook_event.run(str(event.pk))
        event.refresh_from_db()
        self.assertEqual(event.status, WebhookEvent.Status.INVALID)
        self.assertEqual(event.last_error, "ValueError")

    def test_stripe_amount_currency_and_provider_references_are_validated(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        cases = [
            ({"id": "pi-check", "currency": "xaf", "amount": 1}, "amount"),
            ({"id": "pi-check", "currency": "usd", "amount": 5000}, "currency"),
            ({"id": "pi-other", "currency": "xaf", "amount": 5000}, "id"),
        ]
        for verified, _ in cases:
            verified["metadata"] = {"stagelink_payment_id": str(payment.pk)}
        for index, (verified, _) in enumerate(cases):
            event = WebhookEvent.objects.create(
                provider="stripe",
                event_id=f"evt-invalid-{index}",
                event_type="payment_intent.succeeded",
                payload={
                    "id": f"evt-invalid-{index}",
                    "data": {
                        "object": {
                            "id": "pi-check",
                            "metadata": {"stagelink_payment_id": str(payment.pk)},
                        }
                    },
                },
            )
            with patch(
                "stagelink.payments.tasks.StripeService.retrieve_payment_intent",
                return_value=verified,
            ):
                process_webhook_event.run(str(event.pk))
            event.refresh_from_db()
            self.assertEqual(event.status, WebhookEvent.Status.INVALID)

    def test_late_failure_event_cannot_downgrade_successful_payment(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        PaymentService.mark_as_success(payment=payment, provider_payment_id="pi-late")
        event = WebhookEvent(
            provider="stripe",
            event_id="evt-late-failure",
            event_type="payment_intent.payment_failed",
            payload={
                "id": "evt-late-failure",
                "data": {
                    "object": {
                        "id": "pi-late",
                        "metadata": {"stagelink_payment_id": str(payment.pk)},
                    }
                },
            },
        )
        with patch(
            "stagelink.payments.tasks.StripeService.retrieve_payment_intent",
            return_value={
                "id": "pi-late",
                "metadata": {"stagelink_payment_id": str(payment.pk)},
                "currency": "xaf",
                "amount": 5000,
                "status": "succeeded",
            },
        ):
            self.assertEqual(_process_provider_event(event), "ignored")
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCESS)

    def test_duplicate_success_confirmation_is_idempotent(self):
        payment = Payment.objects.create(
            donation=self.donation,
            amount=self.donation.amount,
            provider=PaymentProvider.STRIPE,
            method=PaymentMethod.CARD,
        )
        for _ in range(2):
            PaymentService.mark_as_success(
                payment=payment,
                provider_payment_id="pi-idempotent",
                provider_response={"status": "succeeded"},
            )
        payment.refresh_from_db()
        self.donation.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCESS)
        self.assertEqual(self.donation.status, DonationStatus.COMPLETED)

    def test_recovery_republishes_received_and_expired_processing_only(self):
        pending = WebhookEvent.objects.create(
            provider="stripe",
            event_id="evt-pending",
            event_type="x",
            payload={},
        )
        stale = WebhookEvent.objects.create(
            provider="stripe",
            event_id="evt-stale",
            event_type="x",
            payload={},
            status=WebhookEvent.Status.PROCESSING,
            processing_started_at=timezone.now()
            - PROCESSING_LEASE
            - timedelta(seconds=1),
        )
        fresh = WebhookEvent.objects.create(
            provider="stripe",
            event_id="evt-fresh",
            event_type="x",
            payload={},
            status=WebhookEvent.Status.PROCESSING,
            processing_started_at=timezone.now(),
        )
        terminal = WebhookEvent.objects.create(
            provider="stripe",
            event_id="evt-invalid",
            event_type="x",
            payload={},
            status=WebhookEvent.Status.INVALID,
        )
        with patch("stagelink.payments.tasks.process_webhook_event.delay") as publish:
            reprocess_failed_webhook_events.run()
        self.assertCountEqual(
            [call.args[0] for call in publish.call_args_list],
            [pending.pk, stale.pk],
        )
        self.assertNotIn(fresh.pk, [call.args[0] for call in publish.call_args_list])
        self.assertNotIn(terminal.pk, [call.args[0] for call in publish.call_args_list])

    def test_recovery_survives_redis_publication_failure(self):
        WebhookEvent.objects.create(
            provider="stripe",
            event_id="evt-redis-down",
            event_type="x",
            payload={},
        )
        with patch(
            "stagelink.payments.tasks.process_webhook_event.delay",
            side_effect=RuntimeError("redis unavailable"),
        ):
            reprocess_failed_webhook_events.run()
        self.assertEqual(
            WebhookEvent.objects.get(event_id="evt-redis-down").status,
            WebhookEvent.Status.RECEIVED,
        )


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_ENABLED=True,
    STRIPE_PUBLISHABLE_KEY="pk_test_fake",
    STRIPE_SECRET_KEY="sk_test_fake",  # noqa: S106
    STRIPE_WEBHOOK_SECRET="whsec_test_fake",  # noqa: S106
)
def test_stripe_request_runs_after_database_transaction(client):
    def create_checkout_session(**kwargs):
        assert not connection.in_atomic_block
        return {
            "id": "cs_test",
            "url": "https://checkout.stripe.com/c/pay/test",
            "response": {"status": "open"},
        }

    with patch(
        "stagelink.payments.views.StripeService.create_checkout_session",
        side_effect=create_checkout_session,
    ):
        response = client.post(
            reverse("payments:create"),
            data=json.dumps({"amount": "5000", "provider": "stripe", "method": "card"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="stripe-transaction-test",
        )

    assert response.status_code == HTTPStatus.CREATED


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_ENABLED=True,
    STRIPE_SECRET_KEY="sk_test_fake",  # noqa: S106
    STRIPE_WEBHOOK_SECRET="whsec_test_fake",  # noqa: S106
)
def test_database_error_is_not_misreported_as_provider_502(client):
    with (
        patch(
            "stagelink.payments.views.DonationService.create_donation",
            side_effect=DatabaseError("database unavailable"),
        ),
        pytest.raises(DatabaseError),
    ):
        client.post(
            reverse("payments:create"),
            data=json.dumps({"amount": "5000", "provider": "stripe", "method": "card"}),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="stripe-database-error",
        )


@pytest.mark.django_db(transaction=True)
def test_concurrent_workers_cannot_claim_the_same_webhook():
    event = WebhookEvent.objects.create(
        provider="stripe",
        event_id="evt-concurrent",
        event_type="other",
        payload={},
    )
    entered = Event()
    release = Event()

    def hold_processing(_event):
        entered.set()
        assert release.wait(timeout=5)
        return "ignored"

    def first_worker():
        close_old_connections()
        try:
            process_webhook_event.run(str(event.pk))
        finally:
            close_old_connections()

    with patch(
        "stagelink.payments.tasks._process_provider_event",
        side_effect=hold_processing,
    ) as process:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(first_worker)
            assert entered.wait(timeout=5)
            process_webhook_event.run(str(event.pk))
            release.set()
            future.result(timeout=5)

    event.refresh_from_db()
    assert process.call_count == 1
    assert event.status == WebhookEvent.Status.IGNORED
    assert event.attempts == 1


@pytest.mark.django_db(transaction=True)
@override_settings(
    STRIPE_ENABLED=True,
    STRIPE_PUBLISHABLE_KEY="pk_test_fake",
    STRIPE_SECRET_KEY="sk_test_fake",  # noqa: S106
    STRIPE_WEBHOOK_SECRET="whsec_test_fake",  # noqa: S106
)
def test_stripe_network_verification_runs_outside_database_transaction():
    user = get_user_model().objects.create_user(
        email="outside-transaction@example.com",
        password="test-password",
    )
    donation = DonationService.create_donation(donor=user, amount=Money(5000, "XAF"))
    payment = Payment.objects.create(
        donation=donation,
        amount=donation.amount,
        provider=PaymentProvider.STRIPE,
        method=PaymentMethod.CARD,
    )
    event = WebhookEvent.objects.create(
        provider="stripe",
        event_id="evt-network-boundary",
        event_type="payment_intent.succeeded",
        payload={
            "id": "evt-network-boundary",
            "data": {
                "object": {
                    "id": "pi-boundary",
                    "metadata": {"stagelink_payment_id": str(payment.pk)},
                }
            },
        },
    )

    def retrieve(_intent_id):
        assert not connection.in_atomic_block
        return {
            "id": "pi-boundary",
            "metadata": {"stagelink_payment_id": str(payment.pk)},
            "currency": "xaf",
            "amount": 5000,
            "status": "succeeded",
        }

    with patch(
        "stagelink.payments.tasks.StripeService.retrieve_payment_intent",
        side_effect=retrieve,
    ):
        process_webhook_event.run(str(event.pk))

    event.refresh_from_db()
    payment.refresh_from_db()
    assert event.status == WebhookEvent.Status.PROCESSED
    assert payment.status == PaymentStatus.SUCCESS
