import hmac

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class FlutterwaveService:
    BASE_URL = "https://api.flutterwave.com/v3"

    @classmethod
    def _headers(cls):
        if (
            not settings.FLW_SECRET_KEY.startswith(("FLWSECK_TEST-", "FLWSECK-"))
            or not settings.FLW_WEBHOOK_SECRET
            or any(
                marker in value.lower()
                for value in (settings.FLW_SECRET_KEY, settings.FLW_WEBHOOK_SECRET)
                for marker in ("replace", "xxxxx", "placeholder")
            )
        ):
            raise ValidationError(_("Flutterwave n'est pas configuré."))
        return {
            "Authorization": f"Bearer {settings.FLW_SECRET_KEY}",
            "Content-Type": "application/json",
        }

    @classmethod
    def create_card_payment(
        cls,
        *,
        payment,
        customer_email,
        redirect_url,
    ):
        if not settings.FLUTTERWAVE_ENABLED:
            raise ValidationError(_("Flutterwave est désactivé."))
        if not customer_email:
            raise ValidationError(_("L'adresse e-mail est requise pour Flutterwave."))
        payload = {
            "tx_ref": str(payment.id),
            "amount": str(payment.amount.amount),
            "currency": payment.amount.currency.code,
            "redirect_url": redirect_url,
            "customer": {
                "email": customer_email,
            },
            "meta": {
                "stagelink_payment_id": str(payment.id),
                "donation_id": str(payment.donation_id),
            },
        }

        response = requests.post(
            f"{cls.BASE_URL}/payments",
            headers=cls._headers(),
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("status") != "success":
            raise ValidationError(
                _("Flutterwave n'a pas pu initialiser le paiement."),
            )

        return data

    @classmethod
    def verify_webhook_signature(cls, signature):
        expected = settings.FLW_WEBHOOK_SECRET
        return bool(expected and signature and hmac.compare_digest(expected, signature))

    @classmethod
    def verify_transaction(cls, transaction_id):
        response = requests.get(
            f"{cls.BASE_URL}/transactions/{transaction_id}/verify",
            headers=cls._headers(),
            timeout=20,
        )
        response.raise_for_status()
        return response.json().get("data", {})

    @classmethod
    def create_mobile_money_payment(
        cls,
        *,
        payment,
        customer_email,
        phone_number,
        network,
        redirect_url,
    ):
        if not settings.FLUTTERWAVE_ENABLED:
            raise ValidationError(_("Flutterwave est désactivé."))
        if not customer_email or not phone_number or not network:
            raise ValidationError(
                _("E-mail, téléphone et réseau Mobile Money sont requis."),
            )
        if payment.amount.currency.code != "XAF":
            raise ValidationError(
                _("Mobile Money Flutterwave est configuré en XAF."),
            )
        if payment.amount.amount != payment.amount.amount.to_integral_value():
            raise ValidationError(
                _("Le montant Mobile Money doit être un entier en XAF."),
            )
        payload = {
            "phone_number": phone_number,
            "amount": int(payment.amount.amount),
            "currency": "XAF",
            "country": "CM",
            "email": customer_email,
            "tx_ref": str(payment.id),
            "network": network,
            "redirect_url": redirect_url,
            "meta": {
                "stagelink_payment_id": str(payment.id),
                "donation_id": str(payment.donation_id),
            },
        }

        response = requests.post(
            f"{cls.BASE_URL}/charges?type=mobile_money_franco",
            headers=cls._headers(),
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("status") not in {"success", "pending"}:
            raise ValidationError(
                _("Flutterwave n'a pas pu initialiser le paiement Mobile Money."),
            )

        return data
