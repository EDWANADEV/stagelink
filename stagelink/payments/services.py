from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.money import Money

from stagelink.donation.models import DonationStatus
from stagelink.utils.enums import PaymentMethod
from stagelink.utils.enums import PaymentProvider
from stagelink.utils.enums import PaymentStatus

from .models import Payment


def provider_is_available(provider):
    if provider == PaymentProvider.STRIPE:
        values = (
            settings.STRIPE_PUBLISHABLE_KEY,
            settings.STRIPE_SECRET_KEY,
            settings.STRIPE_WEBHOOK_SECRET,
        )
        return (
            settings.STRIPE_ENABLED
            and settings.STRIPE_PUBLISHABLE_KEY.startswith(("pk_test_", "pk_live_"))
            and settings.STRIPE_SECRET_KEY.startswith(("sk_test_", "sk_live_"))
            and settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_")
            and not any(
                marker in value.lower()
                for value in values
                for marker in ("replace", "xxxxx", "placeholder")
            )
        )
    if provider == PaymentProvider.FLUTTERWAVE:
        values = (settings.FLW_SECRET_KEY, settings.FLW_WEBHOOK_SECRET)
        return (
            settings.FLUTTERWAVE_ENABLED
            and settings.FLW_SECRET_KEY.startswith(("FLWSECK_TEST-", "FLWSECK-"))
            and bool(settings.FLW_WEBHOOK_SECRET)
            and not any(
                marker in value.lower()
                for value in values
                for marker in ("replace", "xxxxx", "placeholder")
            )
        )
    return False


def get_available_payment_methods():
    methods = []
    if provider_is_available(PaymentProvider.STRIPE):
        methods.append((PaymentProvider.STRIPE, PaymentMethod.CARD))
    if provider_is_available(PaymentProvider.FLUTTERWAVE):
        methods.extend(
            [
                (PaymentProvider.FLUTTERWAVE, PaymentMethod.MOBILE_MONEY),
                (PaymentProvider.FLUTTERWAVE, PaymentMethod.CARD),
            ],
        )
    return methods


class PaymentService:
    """
    Business logic for payments.

    Provider-specific implementations should live in dedicated
    provider services.
    """

    @staticmethod
    @transaction.atomic
    def create_payment(*, donation, method, provider, idempotency_key=None):
        if provider == PaymentProvider.STRIPE:
            if not settings.STRIPE_ENABLED:
                raise ValidationError(_("Stripe est désactivé."))
            if not provider_is_available(provider):
                raise ValidationError(_("Stripe n'est pas configuré."))
        elif provider == PaymentProvider.FLUTTERWAVE:
            if not settings.FLUTTERWAVE_ENABLED:
                raise ValidationError(_("Flutterwave est désactivé."))
            if not provider_is_available(provider):
                raise ValidationError(_("Flutterwave n'est pas configuré."))
        else:
            raise ValidationError(_("Prestataire de paiement invalide."))

        if provider == PaymentProvider.STRIPE and method != PaymentMethod.CARD:
            raise ValidationError(
                _("Stripe prend uniquement en charge la carte bancaire."),
            )
        if (
            provider == PaymentProvider.STRIPE
            and donation.amount.currency.code
            in {
                "BIF",
                "CLP",
                "DJF",
                "GNF",
                "JPY",
                "KMF",
                "KRW",
                "MGA",
                "PYG",
                "RWF",
                "UGX",
                "VND",
                "VUV",
                "XAF",
                "XOF",
                "XPF",
            }
            and donation.amount.amount != donation.amount.amount.to_integral_value()
        ):
            raise ValidationError(_("Le montant doit être entier pour cette devise."))
        if provider == PaymentProvider.FLUTTERWAVE and method not in {
            PaymentMethod.CARD,
            PaymentMethod.MOBILE_MONEY,
        }:
            raise ValidationError(_("Méthode Flutterwave invalide."))

        if donation.amount.amount <= 0:
            raise ValidationError(_("Le montant du don doit être supérieur à zéro."))

        if idempotency_key:
            existing = Payment.all_objects.filter(
                provider=provider,
                idempotency_key=idempotency_key,
            ).first()
            if existing:
                if existing.donation_id != donation.pk or existing.method != method:
                    raise ValidationError(
                        _("Cette clé d'idempotence est déjà utilisée."),
                    )
                return existing

        lookup = (
            {"provider": provider, "idempotency_key": idempotency_key}
            if idempotency_key
            else {
                "donation": donation,
                "provider": provider,
            }
        )
        payment, created = Payment.objects.get_or_create(
            **lookup,
            defaults={
                "donation": donation,
                "amount": donation.amount,
                "method": method,
                "provider": provider,
                "status": PaymentStatus.PENDING,
                "metadata": {
                    "donation_id": str(donation.pk),
                },
            },
        )

        if not created:
            if (
                payment.amount != donation.amount
                or payment.provider != provider
                or payment.method != method
            ):
                raise ValidationError(
                    _("Le montant du paiement ne correspond pas au don."),
                )

        return payment

    @staticmethod
    @transaction.atomic
    def mark_as_success(
        *,
        payment,
        provider_payment_id,
        provider_response=None,
    ):
        payment = (
            Payment.all_objects.select_for_update()
            .select_related("donation")
            .get(pk=payment.pk)
        )

        if payment.status in (
            PaymentStatus.REFUNDED,
            PaymentStatus.PARTIALLY_REFUNDED,
        ):
            return payment

        payment.status = PaymentStatus.SUCCESS
        payment.provider_payment_id = provider_payment_id
        payment.processed_at = timezone.now()
        payment.failure_reason = ""

        if provider_response is not None:
            payment.provider_response = provider_response

        payment.save(
            update_fields=[
                "status",
                "provider_payment_id",
                "processed_at",
                "failure_reason",
                "provider_response",
                "updated_at",
            ],
        )

        donation = payment.donation
        donation.status = DonationStatus.COMPLETED
        donation.save(
            update_fields=[
                "status",
                "updated_at",
            ],
        )

        return payment

    @staticmethod
    @transaction.atomic
    def mark_as_failed(
        *,
        payment,
        provider_payment_id=None,
        failure_reason="",
        provider_response=None,
    ):
        payment = (
            Payment.all_objects.select_for_update()
            .select_related("donation")
            .get(pk=payment.pk)
        )

        if payment.status in (
            PaymentStatus.SUCCESS,
            PaymentStatus.REFUNDED,
            PaymentStatus.PARTIALLY_REFUNDED,
        ):
            return payment

        payment.status = PaymentStatus.FAILED
        payment.failure_reason = failure_reason

        if provider_payment_id:
            payment.provider_payment_id = provider_payment_id

        if provider_response is not None:
            payment.provider_response = provider_response

        payment.processed_at = timezone.now()

        payment.save(
            update_fields=[
                "status",
                "failure_reason",
                "provider_payment_id",
                "provider_response",
                "processed_at",
                "updated_at",
            ],
        )

        donation = payment.donation
        donation.status = DonationStatus.FAILED
        donation.save(
            update_fields=[
                "status",
                "updated_at",
            ],
        )

        return payment

    @staticmethod
    @transaction.atomic
    def mark_as_cancelled(*, payment, provider_payment_id=None, provider_response=None):
        payment = (
            Payment.all_objects.select_for_update()
            .select_related("donation")
            .get(pk=payment.pk)
        )
        if payment.status in (
            PaymentStatus.SUCCESS,
            PaymentStatus.REFUNDED,
            PaymentStatus.PARTIALLY_REFUNDED,
        ):
            return payment
        payment.status = PaymentStatus.CANCELLED
        payment.processed_at = timezone.now()
        if provider_payment_id:
            payment.provider_payment_id = provider_payment_id
        if provider_response is not None:
            payment.provider_response = provider_response
        payment.save(
            update_fields=[
                "status",
                "processed_at",
                "provider_payment_id",
                "provider_response",
                "updated_at",
            ],
        )
        payment.donation.status = DonationStatus.CANCELLED
        payment.donation.save(update_fields=["status", "updated_at"])
        return payment

    @staticmethod
    @transaction.atomic
    def sync_refund(
        *,
        payment,
        refunded_amount: Money,
        provider_response=None,
    ):
        payment = (
            Payment.all_objects.select_for_update()
            .select_related("donation")
            .get(pk=payment.pk)
        )

        if refunded_amount.currency != payment.amount.currency:
            raise ValidationError(
                "La devise du remboursement ne correspond pas à celle du paiement.",
            )

        if refunded_amount.amount < Decimal("0"):
            raise ValidationError("Le montant remboursé ne peut pas être négatif.")

        if refunded_amount > payment.amount:
            raise ValidationError(
                "Le montant remboursé ne peut pas dépasser le montant du paiement.",
            )

        payment.refunded_amount = refunded_amount

        if refunded_amount == payment.amount:
            payment.status = PaymentStatus.REFUNDED

        elif refunded_amount > Money(
            "0",
            payment.amount.currency,
        ):
            payment.status = PaymentStatus.PARTIALLY_REFUNDED

        else:
            payment.status = PaymentStatus.SUCCESS

        if provider_response is not None:
            payment.provider_response = provider_response

        payment.save(
            update_fields=[
                "refunded_amount",
                "status",
                "provider_response",
                "updated_at",
            ],
        )

        return payment
