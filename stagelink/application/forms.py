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
