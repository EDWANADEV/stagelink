from django import forms
from django.utils.translation import gettext_lazy as _

from stagelink.core.forms import DesignSystemFormMixin

MAX_INTERVIEW_TURNS = 6


class OfferAssistantForm(DesignSystemFormMixin, forms.Form):
    mode = forms.ChoiceField(
        label=_("Aide recherchée"),
        choices=(
            ("summary", _("Résumer l'offre")),
            ("missions", _("Comprendre les missions")),
            ("skills", _("Expliquer les compétences demandées")),
            ("requirements", _("Clarifier les exigences")),
            ("question", _("Poser une question sur l'offre")),
            ("preparation", _("Recevoir des conseils de préparation")),
            ("interview", _("Préparer un entretien")),
        ),
    )
    question = forms.CharField(
        label=_("Votre question sur le contenu de l'offre"),
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    external_processing_consent = forms.BooleanField(
        label=_(
            "J'accepte l'envoi des informations de l'offre et, si je m'entraîne, "
            "de ma réponse au fournisseur IA pour cette demande.",
        ),
        required=False,
    )
    turn = forms.IntegerField(
        min_value=0,
        max_value=MAX_INTERVIEW_TURNS,
        initial=0,
        widget=forms.HiddenInput,
    )
    previous_question = forms.CharField(required=False, widget=forms.HiddenInput)
    answer = forms.CharField(
        label=_("Votre réponse d'entraînement"),
        required=False,
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("mode") == "question" and not cleaned_data.get(
            "question",
        ):
            self.add_error("question", _("Saisissez votre question sur l'offre."))
        if cleaned_data.get("mode") == "interview" and cleaned_data.get("turn", 0) > 0:
            if not cleaned_data.get("answer", "").strip():
                self.add_error("answer", _("Saisissez une réponse avant de continuer."))
            if not cleaned_data.get("previous_question", "").strip():
                self.add_error(None, _("La question précédente est manquante."))
        return cleaned_data
