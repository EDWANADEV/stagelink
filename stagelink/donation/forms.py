from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _


class DonationForm(forms.Form):
    amount = forms.DecimalField(
        label=_("Montant du don"),
        min_value=Decimal("1"),
        max_digits=12,
        decimal_places=2,
    )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount != amount.to_integral_value():
            raise forms.ValidationError(
                _("Le montant doit être un nombre entier en XAF."),
            )
        return amount
