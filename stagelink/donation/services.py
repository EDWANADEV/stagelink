from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from stagelink.donation.models import Donation
from stagelink.utils.enums import DonationStatus


class DonationService:
    """Services métier liés aux dons."""

    @staticmethod
    @transaction.atomic
    def create_donation(
        *,
        donor=None,
        amount,
    ) -> Donation:
        """Crée un don en attente de paiement."""

        if amount <= 0:
            raise ValidationError(
                _("Le montant du don doit être supérieur à zéro.")
            )

        return Donation.objects.create(
            donor=donor,
            amount=amount,
            status=DonationStatus.PENDING,
            created_by=donor,
        )