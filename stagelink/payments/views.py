import json
import logging
from decimal import InvalidOperation
from uuid import UUID

import requests
import stripe
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from stagelink.donation.forms import DonationForm
from stagelink.donation.services import DonationService
from stagelink.utils.enums import PaymentMethod
from stagelink.utils.enums import PaymentProvider

from .models import Payment
from .providers.flutterwave import FlutterwaveService
from .providers.stripe import StripeService
from .services import PaymentService
from .services import get_available_payment_methods

logger = logging.getLogger(__name__)
MAX_IDEMPOTENCY_KEY_LENGTH = 255


@require_GET
def payment_options(request):
    return JsonResponse(
        {
            "payment_methods": [
                {"provider": provider, "method": method}
                for provider, method in get_available_payment_methods()
            ],
        },
    )


@require_POST
@transaction.non_atomic_requests
def create_payment(request):
    """Create a donation and initialize its PSP checkout; never marks it paid."""
    try:
        data = json.loads(request.body)
        form = DonationForm(data={"amount": data["amount"]})
        if not form.is_valid():
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        amount = form.cleaned_data["amount"]
        provider = data["provider"]
        method = data["method"]
    except ValueError, KeyError, TypeError, InvalidOperation:
        return JsonResponse({"error": "Requête invalide."}, status=400)

    key = request.headers.get("Idempotency-Key")
    if not key or len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        return JsonResponse({"error": "Idempotency-Key est obligatoire."}, status=400)
    try:
        existing = (
            Payment.all_objects.select_related("donation")
            .filter(
                provider=provider,
                idempotency_key=key,
            )
            .first()
        )
        if existing and (existing.amount.amount != amount or existing.method != method):
            return JsonResponse(
                {"error": "Clé d'idempotence réutilisée avec des données différentes."},
                status=409,
            )
        if existing and (existing.provider_payment_id or existing.provider_response):
            response_data = _payment_response(existing)
            if (
                provider == PaymentProvider.STRIPE
                and existing.provider_response.get("checkout_session_id")
            ):
                session = StripeService.retrieve_checkout_session(
                    existing.provider_response["checkout_session_id"],
                )
                if session.status == "open":
                    response_data["checkout_url"] = session.url
            elif provider == PaymentProvider.STRIPE and existing.provider_payment_id:
                intent = StripeService.retrieve_payment_intent(
                    existing.provider_payment_id,
                )
                response_data["client_secret"] = intent.client_secret
            elif provider == PaymentProvider.FLUTTERWAVE:
                response_data["checkout_url"] = existing.provider_response.get(
                    "checkout_url",
                )
            return JsonResponse(response_data, status=200)

        if existing:
            payment = existing
        else:
            with transaction.atomic():
                donation = DonationService.create_donation(
                    donor=request.user if request.user.is_authenticated else None,
                    amount=amount,
                )
                payment = PaymentService.create_payment(
                    donation=donation,
                    method=method,
                    provider=provider,
                    idempotency_key=key,
                )
                if payment.donation_id != donation.pk:
                    donation.delete()
        if provider == PaymentProvider.STRIPE:
            payment_return_url = request.build_absolute_uri(
                reverse("payments:return"),
            )
            success_url = (
                f"{payment_return_url}?payment_id={payment.pk}"
                "&checkout_session_id={CHECKOUT_SESSION_ID}"
            )
            cancel_url = f"{payment_return_url}?payment_id={payment.pk}&cancelled=1"
            email = data.get("email") or (
                request.user.email if request.user.is_authenticated else ""
            )
            result = StripeService.create_checkout_session(
                payment=payment,
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=email,
            )
            if not result.get("url", "").startswith("https://checkout.stripe.com/"):
                raise ValueError("Stripe n'a pas retourné une URL Checkout valide.")
            payment.provider_response = {
                "checkout_session_id": result["id"],
                "checkout_url": result["url"],
                "status": result["response"].get("status"),
            }
            payment.save(
                update_fields=[
                    "provider_response",
                    "updated_at",
                ],
            )
            return JsonResponse(
                {
                    **_payment_response(payment),
                    "checkout_url": result["url"],
                },
                status=201,
            )
        if provider == PaymentProvider.FLUTTERWAVE:
            email = data.get("email") or (
                request.user.email if request.user.is_authenticated else ""
            )
            redirect_url = request.build_absolute_uri(
                f"{reverse('payments:return')}?payment_id={payment.pk}",
            )
            if method == PaymentMethod.MOBILE_MONEY:
                result = FlutterwaveService.create_mobile_money_payment(
                    payment=payment,
                    customer_email=email,
                    phone_number=data.get("phone_number", ""),
                    network=data.get("network", ""),
                    redirect_url=redirect_url,
                )
                result_data = result.get("data", {})
                checkout_url = result_data.get("link")
            else:
                result = FlutterwaveService.create_card_payment(
                    payment=payment,
                    customer_email=email,
                    redirect_url=redirect_url,
                )
                checkout_url = result.get("data", {}).get("link")
            payment.provider_response = {
                "status": result.get("status"),
                "checkout_url": checkout_url,
            }
            payment.save(update_fields=["provider_response", "updated_at"])
            return JsonResponse(
                {**_payment_response(payment), "checkout_url": checkout_url},
                status=201,
            )
    except (ValidationError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except (stripe.StripeError, requests.RequestException) as exc:
        cause = exc.__cause__
        logger.error(
            "Échec de création du paiement provider=%s exception_type=%s "
            "provider_error_code=%s http_status=%s cause_type=%s request_id=%s",
            provider,
            type(exc).__name__,
            getattr(exc, "code", None),
            getattr(exc, "http_status", None),
            type(cause).__name__ if cause else None,
            getattr(exc, "request_id", None),
        )
        return JsonResponse(
            {"error": "Le prestataire de paiement est indisponible."},
            status=502,
        )


def _payment_response(payment):
    return {
        "payment_id": str(payment.pk),
        "donation_id": str(payment.donation_id),
        "status": payment.status,
        "provider": payment.provider,
    }


def payment_return(request):
    """Show the persisted status; browser parameters never change payment state."""
    try:
        payment_id = UUID(request.GET.get("payment_id", ""))
    except ValueError as exc:
        raise Http404 from exc
    payment = get_object_or_404(
        Payment.all_objects.select_related("donation"),
        pk=payment_id,
    )
    if payment.status in {"refunded", "partially_refunded"}:
        payment_status = "success"
    else:
        payment_status = payment.status
    return render(
        request,
        "payments/return.html",
        {"payment": payment, "payment_status": payment_status},
    )
