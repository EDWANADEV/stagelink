from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.forms.fields import MoneyField

from stagelink.profiles.forms import StyledFormMixin
from stagelink.utils.enums import ApplicationMode

from .models import InternshipOffer

from utils.enums import SALARY_CURRENCY_CHOICES

class OfferForm(StyledFormMixin, forms.ModelForm):
    """Saisie d'une offre par une entreprise (création et modification)."""

    # Le modèle stocke une liste JSON ; l'entreprise saisit une liste
    # séparée par des virgules, comme pour les compétences du profil étudiant.
    required_skills = forms.CharField(
        label=_("Compétences recherchées"),
        required=False,
        help_text=_("Séparez les compétences par des virgules."),
        widget=forms.TextInput(
            attrs={"placeholder": _("Python, Communication, Excel")},
        ),
    )

    salary = MoneyField(
        label=_("Rémunération"),
        required=False,
        max_digits=12,
        decimal_places=2,
        default_currency="XAF",
        currency_choices=SALARY_CURRENCY_CHOICES,
        min_value=0,
    )

    class Meta:
        model = InternshipOffer
        fields = (
            "title",
            "description",
            "domain",
            "required_skills",
            "education_level",
            "location",
            "duration_days",
            "start_date",
            "application_deadline",
            "salary",
            "salary_period",
            "available_positions",
            "application_mode",
            "application_url",
        )
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": _("Ex. : Stagiaire développeur web")},
            ),
            "description": forms.Textarea(attrs={"rows": 6}),
            "domain": forms.TextInput(
                attrs={"placeholder": _("Ex. : Informatique, Marketing")},
            ),
            "education_level": forms.TextInput(
                attrs={"placeholder": _("Ex. : Licence 3, Master 1")},
            ),
            "location": forms.TextInput(
                attrs={"placeholder": _("Ex. : Douala")},
            ),
            "start_date": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "application_deadline": forms.DateTimeInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
            "application_url": forms.URLInput(attrs={"placeholder": "https://"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["required_skills"] = ", ".join(
                self.instance.required_skills or [],
            )

    def clean_required_skills(self):
        raw = self.cleaned_data.get("required_skills", "")
        skills = []

        for item in raw.split(","):
            skill = item.strip()
            if skill and skill.lower() not in (s.lower() for s in skills):
                skills.append(skill)

        return skills

    def clean_application_deadline(self):
        deadline = self.cleaned_data["application_deadline"]

        # Une date passée n'est bloquante que si elle a été modifiée :
        # on peut toujours corriger une autre information d'une offre ancienne.
        if (
            "application_deadline" in self.changed_data
            and deadline <= timezone.now()
        ):
            raise forms.ValidationError(
                _("La date limite de candidature doit être dans le futur."),
            )

        return deadline

    def clean_available_positions(self):
        positions = self.cleaned_data["available_positions"]

        if positions < 1:
            raise forms.ValidationError(_("Indiquez au moins une place."))

        return positions

    def clean(self):
        cleaned_data = super().clean()
        salary = cleaned_data.get("salary")

        if salary and not cleaned_data.get("salary_period"):
            self.add_error(
                "salary_period",
                _("Précisez la période de la rémunération."),
            )

        # Une offre interne ne doit pas conserver une URL saisie auparavant.
        if cleaned_data.get("application_mode") == ApplicationMode.INTERNAL:
            cleaned_data["application_url"] = ""

        return cleaned_data


class OfferSearchForm(forms.Form):
    """Recherche et filtres de la liste publique des offres."""

    SORT_RECENT = "recent"
    SORT_DEADLINE = "deadline"
    SORT_CHOICES = (
        (SORT_RECENT, _("Plus récentes")),
        (SORT_DEADLINE, _("Date limite la plus proche")),
    )
    SORT_ORDERING = {
        SORT_RECENT: ("-published_at", "-created_at"),
        SORT_DEADLINE: ("application_deadline",),
    }

    q = forms.CharField(
        label=_("Mots-clés"),
        required=False,
        max_length=100,
        widget=forms.SearchInput(
            attrs={"placeholder": _("Titre, entreprise, compétence…")},
        ),
    )
    domain = forms.ChoiceField(label=_("Domaine"), required=False)
    location = forms.CharField(
        label=_("Lieu"),
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": _("Ex. : Yaoundé")}),
    )
    application_mode = forms.ChoiceField(
        label=_("Candidature"),
        required=False,
        choices=(("", _("Toutes")), *ApplicationMode.choices),
    )
    sort = forms.ChoiceField(
        label=_("Trier par"),
        required=False,
        choices=SORT_CHOICES,
    )

    def __init__(self, *args, domains=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["domain"].choices = [
            ("", _("Tous les domaines")),
            *((domain, domain) for domain in domains),
        ]

        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "block w-full rounded-[10px] border border-border bg-surface "
                "px-3 py-2.5 text-sm text-ink outline-none transition "
                "placeholder:text-[#8A94A6] focus:border-primary "
                "focus:ring-2 focus:ring-primary/20",
            )

    def filter_queryset(self, queryset):
        """Applique la recherche, les filtres et le tri au queryset."""
        # Un filtre invalide (ex. domaine inconnu) est simplement ignoré :
        # cleaned_data ne contient que les champs valides.
        self.is_valid()
        data = self.cleaned_data

        if query := data.get("q", "").strip():
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(domain__icontains=query)
                | Q(required_skills__icontains=query)
                | Q(company__company_name__icontains=query),
            )

        if domain := data.get("domain"):
            queryset = queryset.filter(domain__iexact=domain)

        if location := data.get("location", "").strip():
            queryset = queryset.filter(location__icontains=location)

        if mode := data.get("application_mode"):
            queryset = queryset.filter(application_mode=mode)

        return queryset.order_by(
            *self.SORT_ORDERING[data.get("sort") or self.SORT_RECENT],
        )
