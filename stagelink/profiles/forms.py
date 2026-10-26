from django import forms
from django.utils.translation import gettext_lazy as _

from stagelink.utils.validators import normalize_phone_number

from .models import CompanyProfile, StudentProfile

INPUT_CLASSES = (
    "block w-full rounded-[10px] border border-border bg-surface px-4 py-3 "
    "text-sm text-ink shadow-sm outline-none transition "
    "placeholder:text-[#8A94A6] focus:border-primary focus:ring-2 "
    "focus:ring-primary/20"
)

FILE_CLASSES = (
    "block w-full text-sm text-muted file:mr-4 file:rounded-[10px] "
    "file:border-0 file:bg-background file:px-4 file:py-2.5 "
    "file:text-sm file:font-semibold file:text-primary "
    "hover:file:bg-[#E1E8F2]"
)


class StyledFormMixin:
    """Applique les classes Tailwind de StageLink à tous les champs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.ClearableFileInput):
                widget.attrs.setdefault("class", FILE_CLASSES)
            else:
                widget.attrs.setdefault("class", INPUT_CLASSES)


class StudentProfileForm(StyledFormMixin, forms.ModelForm):
    # Le nom est stocké sur User : il n'est pas demandé à l'inscription,
    # mais il est indispensable pour candidater.
    name = forms.CharField(
        label=_("Nom complet"),
        max_length=255,
    )

    # Le modèle stocke une liste JSON ; l'étudiant saisit une liste
    # séparée par des virgules, plus naturelle qu'un JSON brut.
    skills = forms.CharField(
        label=_("Compétences"),
        required=False,
        help_text=_("Séparez vos compétences par des virgules."),
        widget=forms.TextInput(
            attrs={"placeholder": _("Comptabilité, Excel, Communication")},
        ),
    )

    class Meta:
        model = StudentProfile
        fields = (
            "field_of_study",
            "level",
            "skills",
            "language",
            "cv",
        )
        widgets = {
            "field_of_study": forms.TextInput(
                attrs={"placeholder": _("Ex. : Génie logiciel, Marketing, Droit")},
            ),
            "level": forms.TextInput(
                attrs={"placeholder": _("Ex. : BTS 2, Licence 3, Master 1")},
            ),
            "cv": forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user is not None:
            self.fields["name"].initial = user.name

        if self.instance.pk:
            self.initial["skills"] = ", ".join(self.instance.skills or [])

    def clean_skills(self):
        raw = self.cleaned_data.get("skills", "")
        skills = []

        for skill in raw.split(","):
            skill = skill.strip()
            if skill and skill.lower() not in (s.lower() for s in skills):
                skills.append(skill)

        return skills

    def save(self, commit=True):
        profile = super().save(commit=False)

        if self.user is not None:
            profile.user = self.user
            self.user.name = self.cleaned_data["name"]

        if commit:
            if self.user is not None:
                self.user.save(update_fields=["name"])
            profile.save()

        return profile


class CompanyProfileForm(StyledFormMixin, forms.ModelForm):
    # Saisie libre (espaces acceptés), puis normalisation au format E.164
    # pour respecter la longueur maximale du modèle.
    phone_number = forms.CharField(
        label=_("Numéro de téléphone"),
        max_length=25,
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "+237 6XX XX XX XX", "autocomplete": "tel"},
        ),
    )

    class Meta:
        model = CompanyProfile
        fields = (
            "company_name",
            "description",
            "phone_number",
            "address",
            "website",
            "logo",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "address": forms.TextInput(
                attrs={"placeholder": _("Ex. : Akwa, Douala")},
            ),
            "website": forms.URLInput(attrs={"placeholder": "https://"}),
            "logo": forms.ClearableFileInput(
                attrs={"accept": "image/png,image/jpeg"},
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_phone_number(self):
        return normalize_phone_number(self.cleaned_data.get("phone_number", ""))

    def save(self, commit=True):
        profile = super().save(commit=False)

        if self.user is not None:
            profile.user = self.user

        if commit:
            profile.save()

        return profile
