from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from stagelink.core.models import BaseModel
from stagelink.donation.models import Donation
from stagelink.utils.enums import (
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)


class Payment(BaseModel):
    """
    Represents a payment attempt associated with a donation.

    A payment can be processed by different providers such as
    Flutterwave or Stripe.
    """

    donation = models.OneToOneField(
        Donation,
        on_delete=models.PROTECT,
        related_name="payment",
        verbose_name=_("Don"),
    )

    amount = MoneyField(
        _("Montant"),
        max_digits=12,
        decimal_places=2,
        default_currency="XAF",
    )

    refunded_amount = MoneyField(
        _("Montant remboursé"),
        max_digits=12,
        decimal_places=2,
        default=0,
        default_currency="XAF",
    )

    status = models.CharField(
        _("Statut"),
        max_length=25,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )

    method = models.CharField(
        _("Méthode de paiement"),
        max_length=20,
        choices=PaymentMethod.choices,
    )

    provider = models.CharField(
        _("Prestataire"),
        max_length=20,
        choices=PaymentProvider.choices,
    )

    provider_payment_id = models.CharField(
        _("Identifiant du paiement"),
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text=_(
            "Identifiant de la transaction chez le prestataire."
        ),
    )

    provider_response = models.JSONField(
        _("Réponse du prestataire"),
        default=dict,
        blank=True,
        help_text=_(
            "Réponse brute du prestataire conservée pour l'audit."
        ),
    )

    metadata = models.JSONField(
        _("Métadonnées"),
        default=dict,
        blank=True,
        help_text=_(
            "Informations techniques ou contextuelles supplémentaires."
        ),
    )

    processed_at = models.DateTimeField(
        _("Date de traitement"),
        null=True,
        blank=True,
    )

    failure_reason = models.TextField(
        _("Motif de l'échec"),
        blank=True,
    )

    class Meta:
        verbose_name = _("Paiement")
        verbose_name_plural = _("Paiements")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.donation} - {self.amount} - {self.status}"
