from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from stagelink.core.forms import DesignSystemFormMixin
from stagelink.utils.enums import Role

from .models import CompanyProfile
from .models import StudentProfile

# Séparateur utilisé pour saisir les compétences dans un champ texte.
SKILLS_SEPARATOR = ","


class StudentProfileForm(DesignSystemFormMixin, forms.ModelForm):
    """
    Formulaire de complétion et de modification du profil étudiant.

    Le nom complet est stocké sur User ; il est saisi ici pour
    finaliser l'inscription en une seule étape.
    """

    name = forms.CharField(
        label=_("Nom complet"),
        max_length=255,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "name",
                "placeholder": _("Ex. : Marie Ngono"),
            },
        ),
    )

    skills = forms.CharField(
        label=_("Compétences"),
        required=False,
        help_text=_("Séparez vos compétences par des virgules."),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Ex. : Python, Excel, Communication"),
                "autocomplete": "off",
            },
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
                attrs={
                    "placeholder": _("Ex. : Comptabilité"),
                },
            ),
            "level": forms.TextInput(
                attrs={
                    "placeholder": _("Ex. : BTS 1"),
                },
            ),
            "cv": forms.ClearableFileInput(
                attrs={
                    "accept": ".pdf,application/pdf",
                },
            ),
        }

    field_order = (
        "name",
        "field_of_study",
        "level",
        "skills",
        "language",
        "cv",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Pré-remplit le nom et les compétences existantes.
        if user is not None:
            self.fields["name"].initial = user.name
        if self.instance.pk and self.instance.skills:
            self.initial["skills"] = f"{SKILLS_SEPARATOR} ".join(
                self.instance.skills,
            )

    def clean_name(self) -> str:
        """Supprime les espaces superflus du nom."""
        return " ".join(self.cleaned_data["name"].split())

    def clean_skills(self) -> list[str]:
        """Convertit la saisie en liste de compétences uniques et non vides."""
        raw_skills = self.cleaned_data.get("skills") or ""
        cleaned_skills = []

        for raw_skill in raw_skills.split(SKILLS_SEPARATOR):
            skill = raw_skill.strip()
            if skill and skill.lower() not in (s.lower() for s in cleaned_skills):
                cleaned_skills.append(skill)

        return cleaned_skills


class CompanyProfileForm(DesignSystemFormMixin, forms.ModelForm):
    """Formulaire de complétion et de modification du profil entreprise."""

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
            "company_name": forms.TextInput(
                attrs={
                    "autocomplete": "organization",
                    "placeholder": _("Nom de votre entreprise"),
                },
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": _("Présentez brièvement votre entreprise."),
                },
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "type": "tel",
                    "autocomplete": "tel",
                    "placeholder": _("Ex. : +237 6 99 99 99 99"),
                },
            ),
            "address": forms.TextInput(
                attrs={
                    "autocomplete": "street-address",
                    "placeholder": _("Ville ou adresse de l'entreprise"),
                },
            ),
            "website": forms.URLInput(
                attrs={
                    "autocomplete": "url",
                    "placeholder": "https://example.com",
                },
            ),
            "logo": forms.ClearableFileInput(
                attrs={
                    "accept": "image/jpeg,image/png",
                },
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        # Le paramètre user est accepté pour garder la même signature
        # que StudentProfileForm ; il n'est pas utilisé ici.
        super().__init__(*args, **kwargs)


# Formulaire de profil à utiliser selon le rôle de l'utilisateur.
PROFILE_FORM_BY_ROLE = {
    Role.STUDENT: StudentProfileForm,
    Role.COMPANY: CompanyProfileForm,
}
