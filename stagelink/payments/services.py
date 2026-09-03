from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from djmoney.money import Money

from stagelink.donation.models import DonationStatus
from stagelink.utils.enums import PaymentStatus

from .models import Payment


class PaymentService:
    """
    Business logic for payments.

    Provider-specific implementations should live in dedicated
    provider services.
    """

    @staticmethod
    @transaction.atomic
    def create_payment(*, donation, method, provider):
        if donation.amount <= 0:
            raise ValidationError(
                "Le montant du don doit être supérieur à zéro."
            )

        payment, created = Payment.objects.get_or_create(
            donation=donation,
            defaults={
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
            if payment.amount != donation.amount:
                raise ValidationError(
                    "Le montant du paiement ne correspond pas au don."
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
            Payment.all_objects
            .select_for_update()
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
            ]
        )

        donation = payment.donation
        donation.status = DonationStatus.COMPLETED
        donation.save(
            update_fields=[
                "status",
                "updated_at",
            ]
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
            Payment.all_objects
            .select_for_update()
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
            ]
        )

        donation = payment.donation
        donation.status = DonationStatus.FAILED
        donation.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

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
            Payment.all_objects
            .select_for_update()
            .select_related("donation")
            .get(pk=payment.pk)
        )

        if refunded_amount.currency != payment.amount.currency:
            raise ValidationError(
                "La devise du remboursement ne correspond pas "
                "à celle du paiement."
            )

        if refunded_amount.amount < Decimal("0"):
            raise ValidationError(
                "Le montant remboursé ne peut pas être négatif."
            )

        if refunded_amount > payment.amount:
            raise ValidationError(
                "Le montant remboursé ne peut pas dépasser "
                "le montant du paiement."
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
            ]
        )

        return payment