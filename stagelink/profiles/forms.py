from django import forms
from django.utils.translation import gettext_lazy as _

from .models import CompanyProfile, StudentProfile


class StudentProfileForm(forms.ModelForm):
    """Formulaire de création et de modification du profil étudiant."""

    skills = forms.JSONField(
        label=_("Compétences"),
        required=False,
        initial=list,
        help_text=_(
            'Saisissez une liste JSON, par exemple : '
            '["Python", "Django", "SQL"].'
        ),
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": '["Python", "Django", "SQL"]',
                "autocomplete": "off",
            }
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
                    "autocomplete": "organization-title",
                    "placeholder": _("Ex. : Comptabilité"),
                }
            ),
            "level": forms.TextInput(
                attrs={
                    "placeholder": _("Ex. : BTS 1"),
                }
            ),
            "language": forms.Select(),
            "cv": forms.ClearableFileInput(
                attrs={
                    "accept": ".pdf,application/pdf",
                }
            ),
        }

    def clean_skills(self):
        """Garantit que les compétences sont enregistrées sous forme de liste."""
        skills = self.cleaned_data.get("skills")

        if skills is None or skills == "":
            return []

        if not isinstance(skills, list):
            raise forms.ValidationError(
                _("Les compétences doivent être fournies sous forme de liste.")
            )

        cleaned_skills = []

        for skill in skills:
            if not isinstance(skill, str):
                raise forms.ValidationError(
                    _("Chaque compétence doit être un texte.")
                )

            skill = skill.strip()

            if skill and skill not in cleaned_skills:
                cleaned_skills.append(skill)

        return cleaned_skills


class CompanyProfileForm(forms.ModelForm):
    """Formulaire de création et de modification du profil entreprise."""

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
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": _(
                        "Présentez brièvement votre entreprise."
                    ),
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "type": "tel",
                    "autocomplete": "tel",
                    "placeholder": _("Numéro de téléphone"),
                }
            ),
            "address": forms.TextInput(
                attrs={
                    "autocomplete": "street-address",
                    "placeholder": _("Ville ou adresse de l'entreprise"),
                }
            ),
            "website": forms.URLInput(
                attrs={
                    "autocomplete": "url",
                    "placeholder": "https://example.com",
                }
            ),
            "logo": forms.ClearableFileInput(
                attrs={
                    "accept": "image/jpeg,image/png",
                }
            ),
        }