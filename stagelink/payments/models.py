from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from stagelink.core.models import BaseModel
from stagelink.donation.models import Donation
from stagelink.utils.enums import PaymentMethod
from stagelink.utils.enums import PaymentProvider
from stagelink.utils.enums import PaymentStatus

from .manager import PaymentManager


class Payment(BaseModel):
    """
    Représente une tentative de paiement associée à un don.

    Un même don peut avoir plusieurs tentatives de paiement.
    """

    donation = models.ForeignKey(
        Donation,
        on_delete=models.PROTECT,
        related_name="payments",
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
        help_text=_("Identifiant de la transaction chez le prestataire."),
    )

    idempotency_key = models.CharField(
        _("Clé d'idempotence"),
        max_length=255,
        null=True,
        blank=True,
    )  # noqa: DJ001 -- nullable for rows created before idempotency keys existed

    provider_response = models.JSONField(
        _("Réponse du prestataire"),
        default=dict,
        blank=True,
        help_text=_("Réponse brute du prestataire conservée pour l'audit."),
    )

    metadata = models.JSONField(
        _("Métadonnées"),
        default=dict,
        blank=True,
        help_text=_("Informations techniques ou contextuelles supplémentaires."),
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

    objects = PaymentManager()

    class Meta:
        verbose_name = _("Paiement")
        verbose_name_plural = _("Paiements")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "idempotency_key"],
                name="unique_provider_payment_idempotency_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.donation} - {self.amount} - {self.status}"


class WebhookEvent(models.Model):
    """Durable inbox for authenticated provider events."""

    class Status(models.TextChoices):
        RECEIVED = "received", _("Reçu")
        PROCESSING = "processing", _("En cours")
        PROCESSED = "processed", _("Traité")
        IGNORED = "ignored", _("Ignoré")
        INVALID = "invalid", _("Invalide")
        FAILED = "failed", _("Échoué")

    provider = models.CharField(_("Prestataire"), max_length=20)
    event_id = models.CharField(_("Identifiant événement"), max_length=255)
    event_type = models.CharField(_("Type événement"), max_length=255)
    payload = models.JSONField(_("Événement"))
    received_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RECEIVED,
        db_index=True,
    )
    attempts = models.PositiveIntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    last_dispatched_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "event_id"],
                name="unique_provider_webhook_event",
            ),
        ]
        indexes = [models.Index(fields=["status", "received_at"])]

    def __str__(self):
        return f"{self.provider}:{self.event_id} ({self.status})"
