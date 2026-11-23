from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from stagelink.core.forms import DesignSystemFormMixin

from .models import Review


class ReviewForm(DesignSystemFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        label=_("Note sur StageLink"),
        coerce=int,
        choices=tuple(
            (rating, str(rating))
            for rating in range(
                settings.REVIEW_MIN_RATING,
                settings.REVIEW_MAX_RATING + 1,
            )
        ),
    )

    class Meta:
        model = Review
        fields = ("rating", "comment")
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 5}),
        }

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if not settings.REVIEW_MIN_RATING <= rating <= settings.REVIEW_MAX_RATING:
            raise forms.ValidationError(_("Choisissez une note autorisée."))
        return rating
