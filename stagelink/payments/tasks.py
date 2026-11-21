from decimal import Decimal

from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from stagelink.utils.enums import PaymentProvider

from .models import Payment
from .models import WebhookEvent
from .providers.flutterwave import FlutterwaveService
from .providers.stripe import StripeService
from .services import PaymentService


@shared_task(bind=True, max_retries=8, ignore_result=True)
def process_webhook_event(self, event_pk):
    event = WebhookEvent.objects.get(pk=event_pk)
    if event.status == WebhookEvent.Status.PROCESSED:
        return
    try:
        with transaction.atomic():
            event = WebhookEvent.objects.select_for_update().get(pk=event_pk)
            if event.status in {
                WebhookEvent.Status.PROCESSED,
                WebhookEvent.Status.PROCESSING,
            }:
                return
            event.status = WebhookEvent.Status.PROCESSING
            event.attempts += 1
            event.last_error = ""
            event.save(update_fields=["status", "attempts", "last_error"])
            _process_provider_event(event)
            event.status = WebhookEvent.Status.PROCESSED
            event.processed_at = timezone.now()
            event.last_error = ""
            event.save(update_fields=["status", "processed_at", "last_error"])
    except Exception as exc:  # noqa: BLE001 -- persist every processing failure
        WebhookEvent.objects.filter(pk=event_pk).update(
            attempts=F("attempts") + 1,
        )
        retries = self.request.retries + 1
        status = (
            WebhookEvent.Status.FAILED
            if retries >= self.max_retries
            else WebhookEvent.Status.RECEIVED
        )
        WebhookEvent.objects.filter(pk=event_pk).update(
            status=status,
            last_error=str(exc)[:4000],
        )
        if status == WebhookEvent.Status.FAILED:
            return
        raise self.retry(
            exc=exc,
            countdown=min(30 * (2**self.request.retries), 3600),
        ) from exc


def _process_provider_event(event):
    body = event.payload
    if event.provider == PaymentProvider.STRIPE:
        data = body["data"]["object"]
        payment_id = data.get("metadata", {}).get("stagelink_payment_id")
        if not payment_id:
            return
        payment = Payment.all_objects.select_related("donation").get(pk=payment_id)
        if payment.provider != PaymentProvider.STRIPE:
            raise ValueError("Le paiement ne correspond pas au prestataire.")

        if event.event_type in {
            "checkout.session.completed",
            "checkout.session.expired",
        }:
            session = StripeService.retrieve_checkout_session(data["id"])
            verified_session = (
                session.to_dict() if hasattr(session, "to_dict") else dict(session)
            )
            if (
                verified_session.get("metadata", {}).get("stagelink_payment_id")
                != str(payment.pk)
            ):
                raise ValueError("Métadonnées Checkout Stripe incohérentes.")
            if verified_session.get("currency", "").upper() != payment.amount.currency.code:
                raise ValueError("Devise Checkout Stripe incorrecte.")
            expected_amount = StripeService.amount_in_minor_units(payment)
            if verified_session.get("amount_total") != expected_amount:
                raise ValueError("Montant Checkout Stripe incorrect.")

            if (
                event.event_type == "checkout.session.expired"
                and verified_session.get("status") == "expired"
            ):
                PaymentService.mark_as_cancelled(
                    payment=payment,
                    provider_payment_id=verified_session["id"],
                    provider_response={
                        "event_id": body["id"],
                        "checkout_session_id": verified_session["id"],
                        "status": "expired",
                    },
                )
                return

            if (
                event.event_type == "checkout.session.completed"
                and verified_session.get("status") == "complete"
                and verified_session.get("payment_status") == "paid"
            ):
                payment_intent_id = verified_session.get("payment_intent")
                if not payment_intent_id:
                    raise ValueError("Checkout Stripe sans PaymentIntent.")
                intent = StripeService.retrieve_payment_intent(payment_intent_id)
                verified_intent = (
                    intent.to_dict() if hasattr(intent, "to_dict") else dict(intent)
                )
                _verify_stripe_intent(payment, verified_intent, expected_amount)
                if verified_intent.get("status") != "succeeded":
                    raise ValueError("PaymentIntent Stripe non confirmé.")
                PaymentService.mark_as_success(
                    payment=payment,
                    provider_payment_id=payment_intent_id,
                    provider_response={
                        "event_id": body["id"],
                        "checkout_session_id": verified_session["id"],
                        "status": "succeeded",
                    },
                )
            return

        pi = StripeService.retrieve_payment_intent(data["id"])
        verified = pi.to_dict() if hasattr(pi, "to_dict") else dict(pi)
        expected = StripeService.amount_in_minor_units(payment)
        _verify_stripe_intent(payment, verified, expected)
        if (
            event.event_type == "payment_intent.succeeded"
            and verified.get("status") == "succeeded"
        ):
            PaymentService.mark_as_success(
                payment=payment,
                provider_payment_id=data["id"],
                provider_response={
                    "event_id": body["id"],
                    "status": verified["status"],
                },
            )
        elif event.event_type in {
            "payment_intent.payment_failed",
            "payment_intent.canceled",
        }:
            if verified.get("status") == "canceled":
                PaymentService.mark_as_cancelled(
                    payment=payment,
                    provider_payment_id=data["id"],
                    provider_response={"event_id": body["id"], "status": "canceled"},
                )
            elif verified.get("status") == "requires_payment_method":
                PaymentService.mark_as_failed(
                    payment=payment,
                    provider_payment_id=data["id"],
                    failure_reason=verified.get("last_payment_error", {}).get(
                        "message",
                        verified.get("status", "Échec"),
                    ),
                    provider_response={
                        "event_id": body["id"],
                        "status": verified["status"],
                    },
                )
        return

    data = body["data"]
    tx_ref = data.get("tx_ref")
    payment = Payment.all_objects.select_related("donation").get(pk=tx_ref)
    if payment.provider != PaymentProvider.FLUTTERWAVE:
        raise ValueError("Le paiement ne correspond pas au prestataire.")
    verified = FlutterwaveService.verify_transaction(data["id"])
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
            provider_response={
                "event_id": str(body.get("id")),
                "status": verified["status"],
            },
        )


def _verify_stripe_intent(payment, verified, expected_amount):
    if verified.get("metadata", {}).get("stagelink_payment_id") != str(payment.pk):
        raise ValueError("Métadonnées Stripe incohérentes.")
    if verified.get("currency", "").upper() != payment.amount.currency.code:
        raise ValueError("Devise Stripe incorrecte.")
    if verified.get("amount") != expected_amount:
        raise ValueError("Montant Stripe incorrect.")


@shared_task(ignore_result=True)
def reprocess_failed_webhook_events():
    """Periodic recovery for durable events after broker/worker outages."""
    ids = WebhookEvent.objects.filter(
        status__in=[WebhookEvent.Status.RECEIVED, WebhookEvent.Status.FAILED],
        attempts__lt=16,
    ).values_list("pk", flat=True)[:500]
    for event_id in ids:
        process_webhook_event.delay(event_id)
