from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from djmoney.money import Money

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

        if isinstance(amount, Money):
            if amount.currency.code != "XAF":
                raise ValidationError(_("Les dons sont actuellement libellés en XAF."))
            amount = amount.amount
        else:
            try:
                amount = Decimal(str(amount))
            except (TypeError, ValueError, ArithmeticError) as exc:
                raise ValidationError(_("Saisissez un montant valide.")) from exc

        if not amount.is_finite() or amount <= 0:
            raise ValidationError(_("Le montant du don doit être supérieur à zéro."))
        if amount != amount.to_integral_value():
            raise ValidationError(
                _("Le montant du don doit être un nombre entier en XAF."),
            )

        return Donation.objects.create(
            donor=donor,
            amount=amount,
            status=DonationStatus.PENDING,
            created_by=donor,
        )
