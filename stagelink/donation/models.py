from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from stagelink.core.models import BaseModel
from stagelink.utils.enums import DonationStatus
from .managers import DonationManager

class Donation(BaseModel):
    """Don volontaire effectué pour soutenir StageLink."""

    donor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="donations",
        verbose_name=_("Donateur"),
    )

    amount = MoneyField(
        _("Montant"),
        max_digits=12,
        decimal_places=2,
        default_currency="XAF",
    )

    status = models.CharField(
        _("Statut"),
        max_length=20,
        choices=DonationStatus.choices,
        default=DonationStatus.PENDING,
        db_index=True,
    )

    objects = DonationManager()

    class Meta:
        verbose_name = _("Don")
        verbose_name_plural = _("Dons")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        donor = self.donor.email if self.donor else _("Anonyme")
        return f"{donor} - {self.amount}"
