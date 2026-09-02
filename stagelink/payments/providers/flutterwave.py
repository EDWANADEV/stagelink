import requests
from django.conf import settings
from django.core.exceptions import ValidationError


class FlutterwaveService:
    BASE_URL = "https://api.flutterwave.com/v3"

    @classmethod
    def _headers(cls):
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
                "Flutterwave n'a pas pu initialiser le paiement."
            )

        return data

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
                "Flutterwave n'a pas pu initialiser le paiement Mobile Money."
            )

        return data