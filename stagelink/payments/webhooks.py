import json

import stripe
from django.conf import settings
from django.db import IntegrityError
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import WebhookEvent
from .providers.flutterwave import FlutterwaveService
from .tasks import process_webhook_event


def _persist_event(*, provider, event_id, event_type, payload):
    try:
        with transaction.atomic():
            event, created = WebhookEvent.objects.get_or_create(
                provider=provider,
                event_id=event_id,
                defaults={"event_type": event_type, "payload": payload},
            )
            if created:
                transaction.on_commit(lambda: process_webhook_event.delay(event.pk))
    except IntegrityError:
        # A concurrent delivery won the unique constraint race.
        return HttpResponse(status=200)
    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            request.headers.get("Stripe-Signature"),
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError, stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    if (
        not isinstance(event.get("id"), str)
        or not isinstance(event.get("type"), str)
        or not isinstance(event.get("data"), dict)
        or not isinstance(event["data"].get("object"), dict)
    ):
        return HttpResponse(status=400)
    event = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    return _persist_event(
        provider="stripe",
        event_id=event["id"],
        event_type=event.get("type", ""),
        payload=event,
    )


@csrf_exempt
@require_POST
def flutterwave_webhook(request):
    if not FlutterwaveService.verify_webhook_signature(
        request.headers.get("verif-hash"),
    ):
        return HttpResponse(status=400)
    try:
        payload = json.loads(request.body)
        data = payload.get("data")
        event_type = payload.get("event")
        if not isinstance(data, dict):
            return HttpResponse(status=400)
        transaction_id = data.get("id")
        event_id = payload.get("id")
        if event_id is None and transaction_id is not None and event_type:
            event_id = f"{event_type}:{transaction_id}"
        if (
            not isinstance(event_id, (str, int))
            or not isinstance(event_type, str)
            or not event_type
            or not isinstance(transaction_id, (str, int))
            or not isinstance(data.get("tx_ref"), str)
        ):
            return HttpResponse(status=400)
    except ValueError, AttributeError:
        return HttpResponse(status=400)
    return _persist_event(
        provider="flutterwave",
        event_id=str(event_id),
        event_type=event_type,
        payload=payload,
    )
