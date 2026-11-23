"""Durable processing for payment provider webhook events."""

# Validation errors carry short, controlled descriptions used only in the inbox.
# ruff: noqa: EM101, TRY003

import logging
from datetime import timedelta
from decimal import Decimal

import stripe
from celery import shared_task
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.db.models import Q
from django.utils import timezone

from stagelink.utils.enums import PaymentProvider

from .models import Payment
from .models import WebhookEvent
from .providers.flutterwave import FlutterwaveService
from .providers.stripe import StripeService
from .services import PaymentService

logger = logging.getLogger(__name__)
MAX_WEBHOOK_ATTEMPTS = 8
PROCESSING_LEASE = timedelta(minutes=10)
DISPATCH_COOLDOWN = timedelta(minutes=5)
SUPPORTED_STRIPE_EVENTS = {
    "checkout.session.completed",
    "checkout.session.expired",
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "payment_intent.canceled",
}


@shared_task(bind=True, ignore_result=True)
def process_webhook_event(self, event_pk):
    """Claim one durable inbox row, verify externally, then apply business state."""
    now = timezone.now()
    stale_before = now - PROCESSING_LEASE
    with transaction.atomic():
        claimed = (
            WebhookEvent.objects.filter(pk=event_pk, attempts__lt=MAX_WEBHOOK_ATTEMPTS)
            .filter(
                Q(status=WebhookEvent.Status.RECEIVED)
                | Q(
                    status=WebhookEvent.Status.PROCESSING,
                    processing_started_at__lt=stale_before,
                ),
            )
            .update(
                status=WebhookEvent.Status.PROCESSING,
                processing_started_at=now,
                attempts=F("attempts") + 1,
                last_error="",
            )
        )
    if not claimed:
        return

    event = WebhookEvent.objects.get(pk=event_pk)
    logger.info(
        "Webhook processing started provider=%s event_id=%s type=%s attempt=%s",
        event.provider,
        event.event_id,
        event.event_type,
        event.attempts,
    )
    try:
        outcome = _process_provider_event(event)
    except (
        ValueError,
        ValidationError,
        Payment.DoesNotExist,
        stripe.InvalidRequestError,
        KeyError,
        TypeError,
    ) as exc:
        _finish_event(event, WebhookEvent.Status.INVALID, type(exc).__name__)
        logger.warning(
            "Webhook permanently invalid provider=%s event_id=%s type=%s error_type=%s",
            event.provider,
            event.event_id,
            event.event_type,
            type(exc).__name__,
        )
        return
    except Exception as exc:  # noqa: BLE001 -- provider SDK errors vary by adapter.
        terminal = event.attempts >= MAX_WEBHOOK_ATTEMPTS
        status = (
            WebhookEvent.Status.FAILED if terminal else WebhookEvent.Status.RECEIVED
        )
        _finish_event(event, status, type(exc).__name__)
        logger.warning(
            "Webhook processing failed provider=%s event_id=%s type=%s "
            "attempt=%s terminal=%s",
            event.provider,
            event.event_id,
            event.event_type,
            event.attempts,
            terminal,
            extra={"error_type": type(exc).__name__},
        )
        return

    if outcome == "ignored":
        status = WebhookEvent.Status.IGNORED
    elif outcome == "processed":
        status = WebhookEvent.Status.PROCESSED
    else:
        # A missing/no-op result is never treated as a successful confirmation.
        status = WebhookEvent.Status.INVALID
        outcome = "invalid"
    _finish_event(event, status)
    logger.info(
        "Webhook processing finished provider=%s event_id=%s type=%s result=%s",
        event.provider,
        event.event_id,
        event.event_type,
        outcome,
    )


def _finish_event(event, status, error=""):
    WebhookEvent.objects.filter(
        pk=event.pk,
        status=WebhookEvent.Status.PROCESSING,
    ).update(
        status=status,
        processed_at=timezone.now()
        if status
        in {
            WebhookEvent.Status.PROCESSED,
            WebhookEvent.Status.IGNORED,
        }
        else None,
        processing_started_at=None,
        last_error=error[:4000],
    )


def _as_dict(value):
    return value.to_dict() if hasattr(value, "to_dict") else dict(value)


def _process_provider_event(event):
    if event.provider == PaymentProvider.STRIPE:
        return _process_stripe_event(event)
    if event.provider != PaymentProvider.FLUTTERWAVE:
        return "ignored"
    return _process_flutterwave_event(event)


def _get_payment(payment_id, provider):
    if not payment_id:
        raise ValueError("Référence StageLink absente de l'événement.")
    try:
        payment = Payment.all_objects.select_related("donation").get(pk=payment_id)
    except (Payment.DoesNotExist, ValueError) as exc:
        raise ValueError("Référence de paiement StageLink inconnue.") from exc
    if payment.provider != provider:
        raise ValueError("Le paiement ne correspond pas au prestataire.")
    return payment


def _process_stripe_event(event):
    if event.event_type not in SUPPORTED_STRIPE_EVENTS:
        return "ignored"
    body = event.payload
    data = body.get("data", {}).get("object", {})
    payment_id = data.get("metadata", {}).get("stagelink_payment_id")
    if not payment_id:
        raise ValueError("Événement Stripe sans stagelink_payment_id.")
    payment = _get_payment(payment_id, PaymentProvider.STRIPE)
    if event.event_type.startswith("checkout.session."):
        return _process_checkout_event(event, payment, data)
    return _process_intent_event(event, payment, data)


def _process_checkout_event(event, payment, data):  # noqa: C901
    body = event.payload
    session_id = data.get("id", "")
    verified = _as_dict(StripeService.retrieve_checkout_session(session_id))
    if verified.get("id") != session_id:
        raise ValueError("Référence Checkout Stripe incohérente.")
    if verified.get("metadata", {}).get("stagelink_payment_id") != str(payment.pk):
        raise ValueError("Métadonnées Checkout Stripe incohérentes.")
    if verified.get("currency", "").upper() != payment.amount.currency.code:
        raise ValueError("Devise Checkout Stripe incorrecte.")
    expected = StripeService.amount_in_minor_units(payment)
    if verified.get("amount_total") != expected:
        raise ValueError("Montant Checkout Stripe incorrect.")
    if event.event_type == "checkout.session.expired":
        if verified.get("status") != "expired":
            return "ignored"
        PaymentService.mark_as_cancelled(
            payment=payment,
            provider_payment_id=verified["id"],
            provider_response={"event_id": body["id"], "status": "expired"},
        )
        return "processed"
    if verified.get("status") != "complete" or verified.get("payment_status") != "paid":
        return "ignored"
    intent_id = verified.get("payment_intent")
    if not intent_id:
        raise ValueError("Checkout Stripe sans PaymentIntent.")
    intent = _as_dict(StripeService.retrieve_payment_intent(intent_id))
    _verify_stripe_intent(payment, intent, expected)
    if intent.get("id") != intent_id:
        raise ValueError("Référence PaymentIntent incohérente.")
    if intent.get("status") != "succeeded":
        return "ignored"
    PaymentService.mark_as_success(
        payment=payment,
        provider_payment_id=intent_id,
        provider_response={
            "event_id": body["id"],
            "checkout_session_id": verified["id"],
            "status": "succeeded",
        },
    )
    return "processed"


def _process_intent_event(event, payment, data):
    intent_id = data.get("id", "")
    verified = _as_dict(StripeService.retrieve_payment_intent(intent_id))
    if verified.get("id") != intent_id:
        raise ValueError("Référence PaymentIntent incohérente.")
    _verify_stripe_intent(
        payment,
        verified,
        StripeService.amount_in_minor_units(payment),
    )
    body = event.payload
    if event.event_type == "payment_intent.succeeded":
        if verified.get("status") != "succeeded":
            return "ignored"
        PaymentService.mark_as_success(
            payment=payment,
            provider_payment_id=intent_id,
            provider_response={"event_id": body["id"], "status": verified["status"]},
        )
        return "processed"
    if event.event_type == "payment_intent.canceled":
        if verified.get("status") != "canceled":
            return "ignored"
        PaymentService.mark_as_cancelled(
            payment=payment,
            provider_payment_id=intent_id,
            provider_response={"event_id": body["id"], "status": "canceled"},
        )
        return "processed"
    if verified.get("status") != "requires_payment_method":
        return "ignored"
    PaymentService.mark_as_failed(
        payment=payment,
        provider_payment_id=intent_id,
        failure_reason=verified.get("last_payment_error", {}).get("message", "Échec"),
        provider_response={"event_id": body["id"], "status": verified["status"]},
    )
    return "processed"


def _process_flutterwave_event(event):
    body = event.payload
    data = body.get("data", {})
    payment_id = data.get("tx_ref")
    payment = _get_payment(payment_id, PaymentProvider.FLUTTERWAVE)
    verified = FlutterwaveService.verify_transaction(data.get("id"))
    if str(verified.get("tx_ref")) != str(payment.pk):
        raise ValueError("Référence Flutterwave incorrecte.")
    if verified.get("currency", "").upper() != payment.amount.currency.code:
        raise ValueError("Devise Flutterwave incorrecte.")
    if Decimal(str(verified.get("amount", "0"))) != payment.amount.amount:
        raise ValueError("Montant Flutterwave incorrect.")
    if verified.get("status") == "successful":
        PaymentService.mark_as_success(
            payment=payment,
            provider_payment_id=str(verified["id"]),
            provider_response={"event_id": str(body.get("id")), "status": "successful"},
        )
    elif verified.get("status") == "cancelled":
        PaymentService.mark_as_cancelled(
            payment=payment,
            provider_payment_id=str(verified["id"]),
            provider_response={"event_id": str(body.get("id")), "status": "cancelled"},
        )
    elif verified.get("status") == "failed":
        PaymentService.mark_as_failed(
            payment=payment,
            provider_payment_id=str(verified["id"]),
            failure_reason=verified.get("processor_response", "Paiement échoué."),
            provider_response={"event_id": str(body.get("id")), "status": "failed"},
        )
    else:
        return "ignored"
    return "processed"


def _verify_stripe_intent(payment, verified, expected_amount):
    if verified.get("metadata", {}).get("stagelink_payment_id") != str(payment.pk):
        raise ValueError("Métadonnées Stripe incohérentes.")
    if verified.get("currency", "").upper() != payment.amount.currency.code:
        raise ValueError("Devise Stripe incorrecte.")
    if verified.get("amount") != expected_amount:
        raise ValueError("Montant Stripe incorrect.")


def publish_webhook_event(event):
    """Publish one pending event, respecting a short duplicate-dispatch cooldown."""
    now = timezone.now()
    cooldown = now - DISPATCH_COOLDOWN
    reservation = Q(
        pk=event.pk,
        status=WebhookEvent.Status.RECEIVED,
    ) | Q(
        pk=event.pk,
        status=WebhookEvent.Status.PROCESSING,
        processing_started_at__lt=now - PROCESSING_LEASE,
    )
    with transaction.atomic():
        reserved = (
            WebhookEvent.objects.filter(reservation)
            .filter(
                Q(last_dispatched_at__isnull=True) | Q(last_dispatched_at__lt=cooldown),
            )
            .update(last_dispatched_at=now)
        )
    if not reserved:
        return False
    try:
        process_webhook_event.delay(event.pk)
    except Exception:  # noqa: BLE001 -- broker client exceptions vary by transport.
        WebhookEvent.objects.filter(
            pk=event.pk,
            last_dispatched_at=now,
            status__in=[WebhookEvent.Status.RECEIVED, WebhookEvent.Status.PROCESSING],
        ).update(last_dispatched_at=None)
        logger.warning(
            "Webhook task publication failed provider=%s event_id=%s type=%s "
            "error_type=%s",
            event.provider,
            event.event_id,
            event.event_type,
            "BrokerError",
        )
        return False
    logger.info(
        "Webhook task published provider=%s event_id=%s type=%s",
        event.provider,
        event.event_id,
        event.event_type,
    )
    return True


@shared_task(ignore_result=True)
def reprocess_failed_webhook_events():
    """Republish durable pending events and reclaim expired worker leases."""
    stale_before = timezone.now() - PROCESSING_LEASE
    WebhookEvent.objects.filter(
        status=WebhookEvent.Status.PROCESSING,
        attempts__gte=MAX_WEBHOOK_ATTEMPTS,
        processing_started_at__lt=stale_before,
    ).update(
        status=WebhookEvent.Status.FAILED,
        processing_started_at=None,
        last_error="Worker lease expired at the retry limit.",
    )
    WebhookEvent.objects.filter(
        status=WebhookEvent.Status.RECEIVED,
        attempts__gte=MAX_WEBHOOK_ATTEMPTS,
    ).update(
        status=WebhookEvent.Status.FAILED,
        last_error="Retry limit reached.",
    )
    eligible = (
        WebhookEvent.objects.filter(attempts__lt=MAX_WEBHOOK_ATTEMPTS)
        .filter(
            Q(status=WebhookEvent.Status.RECEIVED)
            | Q(
                status=WebhookEvent.Status.PROCESSING,
                processing_started_at__lt=stale_before,
            ),
        )
        .filter(
            Q(last_dispatched_at__isnull=True)
            | Q(last_dispatched_at__lt=timezone.now() - DISPATCH_COOLDOWN),
        )
        .order_by("received_at")
        .only(
            "pk",
            "provider",
            "event_id",
            "event_type",
            "status",
            "processing_started_at",
            "last_dispatched_at",
        )[:100]
    )
    published = 0
    for event in eligible:
        published += publish_webhook_event(event)
    logger.info("Webhook recovery publication finished published=%s", published)
