from django import forms
from django.utils.translation import gettext_lazy as _

from stagelink.utils.enums import ApplicationStatus

from .services import ApplicationService


class ApplicationSubmissionForm(forms.Form):
    cover_letter = forms.CharField(
        label=_("Lettre de motivation"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
    )
    assistant_task = forms.ChoiceField(
        label=_("Type d'amélioration"),
        required=False,
        choices=(
            ("proofread", _("Corriger la langue")),
            ("clarity", _("Améliorer la clarté")),
            ("structure", _("Améliorer la structure")),
            ("adapt", _("Mettre en évidence les points liés à l'offre")),
        ),
        initial="proofread",
    )
    assistant_tone = forms.ChoiceField(
        label=_("Ton souhaité"),
        required=False,
        choices=(
            ("professional", _("Professionnel")),
            ("direct", _("Direct")),
            ("warm", _("Chaleureux")),
        ),
        initial="professional",
    )
    assistant_length = forms.ChoiceField(
        label=_("Longueur souhaitée"),
        required=False,
        choices=(
            ("similar", _("Conserver une longueur proche")),
            ("shorter", _("Plus concise")),
            ("longer", _("Plus développée")),
        ),
        initial="similar",
    )

    def __init__(self, *args, student_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student_profile = student_profile

    def clean(self):
        cleaned_data = super().clean()
        if self.student_profile is not None and not self.student_profile.cv:
            raise forms.ValidationError(
                _("Ajoutez un CV à votre profil avant de postuler."),
            )
        return cleaned_data


class ApplicationStatusForm(forms.Form):
    status = forms.ChoiceField(label=_("Nouveau statut"))
    interview_at = forms.DateTimeField(
        label=_("Date et heure de l'entretien"),
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    def __init__(self, *args, application, **kwargs):
        super().__init__(*args, **kwargs)
        transitions = ApplicationService.ALLOWED_TRANSITIONS[application.status]
        # Le retrait est réservé au parcours dédié de l'étudiant.
        transitions = transitions - {ApplicationStatus.WITHDRAWN}
        self.fields["status"].choices = [
            (status.value, status.label)
            for status in ApplicationStatus
            if status in transitions
        ]

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get(
            "status",
        ) == ApplicationStatus.INTERVIEW and not cleaned_data.get("interview_at"):
            self.add_error(
                "interview_at",
                _("Indiquez la date et l'heure prévues pour l'entretien."),
            )
        return cleaned_data


class ApplicationWithdrawalForm(forms.Form):
    reason = forms.CharField(
        label=_("Motif du retrait"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def __init__(self, *args, application, **kwargs):
        super().__init__(*args, **kwargs)
        if application.status == ApplicationStatus.INTERVIEW:
            self.fields["reason"].required = True
