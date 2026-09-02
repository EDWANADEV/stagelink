import json
import logging

import stagelink.payments.providers.stripe as stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Payment
from .services import PaymentService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    signature = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    event_type = event["type"]
    data = event["data"]["object"]

    metadata = data.get("metadata", {})
    payment_id = metadata.get("stagelink_payment_id")

    if not payment_id:
        return HttpResponse(status=200)

    try:
        payment = Payment.all_objects.get(pk=payment_id)
    except Payment.DoesNotExist:
        logger.warning(
            "Paiement StageLink introuvable: %s",
            payment_id,
        )
        return HttpResponse(status=200)

    provider_response = {
        "event_id": event["id"],
        "event_type": event_type,
        "data": data,
    }

    if event_type == "payment_intent.succeeded":
        PaymentService.mark_as_success(
            payment=payment,
            provider_payment_id=data["id"],
            provider_response=provider_response,
        )

    elif event_type == "payment_intent.payment_failed":
        error = data.get("last_payment_error") or {}

        PaymentService.mark_as_failed(
            payment=payment,
            provider_payment_id=data["id"],
            failure_reason=error.get(
                "message",
                "Le paiement a échoué.",
            ),
            provider_response=provider_response,
        )

    elif event_type == "payment_intent.canceled":
        PaymentService.mark_as_failed(
            payment=payment,
            provider_payment_id=data["id"],
            failure_reason="Paiement annulé.",
            provider_response=provider_response,
        )

    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def flutterwave_webhook(request):
    # La vérification exacte de la signature/token Flutterwave
    # sera effectuée ici avant tout traitement.
    payload = json.loads(request.body)

    # TODO:
    # 1. Vérifier l'authenticité du webhook.
    # 2. Récupérer tx_ref.
    # 3. Vérifier la transaction directement auprès de Flutterwave.
    # 4. Vérifier montant + devise.
    # 5. Mettre Payment à jour.
    # 6. Retourner HTTP 200.

    logger.info(
        "Webhook Flutterwave reçu: %s",
        payload,
    )

    return HttpResponse(status=200)