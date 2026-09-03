from django.core.exceptions import ValidationError
from django.db import models

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField

from stagelink.core.models import BaseModel
from stagelink.profiles.models import CompanyProfile
from stagelink.utils.enums import OfferStatus
from stagelink.utils.enums import ApplicationMode
from stagelink.utils.enums import SalaryPeriod

from .managers import InternshipOfferManager



class InternshipOffer(BaseModel):
    """Modèle représentant une offre de stage sur StageLink."""

    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="internship_offers",
        verbose_name=_("Entreprise"),
    )
    title = models.CharField(
        _("Titre"),
        max_length=255,
    )

    description = models.TextField(
        _("Description"),
    )

    domain = models.CharField(
        _("Domaine"),
        max_length=150,
        db_index=True,
    )

    required_skills = models.JSONField(
        _("Compétences recherchées"),
        default=list,
        blank=True,
    )

    education_level = models.CharField(
        _("Niveau d'études"),
        max_length=100,
        blank=True,
    )

    location = models.CharField(
        _("Lieu du stage"),
        max_length=255,
    )

    duration_days = models.PositiveIntegerField(
        _("Durée du stage en jours"),
    )

    start_date = models.DateField(
        _("Date de début"),
        null=True,
        blank=True,
    )

    application_deadline = models.DateTimeField(
        _("Date limite de candidature"),
        db_index=True,
    )

    salary = MoneyField(
        _("Rémunération"),
        max_digits=12,
        decimal_places=2,
        default_currency="XAF",
        null=True,
        blank=True,
    )

    salary_period = models.CharField(
        _("Période de rémunération"),
        max_length=10,
        choices=SalaryPeriod.choices,
        blank=True,
    )

    available_positions = models.PositiveIntegerField(
        _("Nombre de places"),
        default=1,
    )

    status = models.CharField(
        _("Statut"),
        max_length=20,
        choices=OfferStatus.choices,
        default=OfferStatus.DRAFT,
        db_index=True,
    )

    published_at = models.DateTimeField(
        _("Date de publication"),
        null=True,
        blank=True,
        db_index=True,
    )
    application_mode = models.CharField(
        _("Mode de candidature"),
        max_length=10,
        choices=ApplicationMode.choices,
        default=ApplicationMode.INTERNAL,
    )

    application_url = models.URLField(
        _("URL de candidature externe"),
        blank=True,
    )
    objects = InternshipOfferManager()

    class Meta:
        verbose_name = _("Offre de stage")
        verbose_name_plural = _("Offres de stage")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        """Valide la cohérence du mode de candidature."""

        super().clean()

        if (
            self.application_mode == ApplicationMode.EXTERNAL
            and not self.application_url
        ):
            raise ValidationError(
                {
                    "application_url": _(
                        "Une URL est requise pour une candidature externe.",
                    ),
                },
            )

        if (
            self.application_mode == ApplicationMode.INTERNAL
            and self.application_url
        ):
            raise ValidationError(
                {
                    "application_url": _(
                        "Une candidature interne ne doit pas avoir d'URL externe.",
                    ),
                },
            )

    @property
    def formatted_duration(self) -> str:
        """Retourne la durée dans un format lisible pour l'utilisateur."""
        if self.duration_days < 7:
            return _("%(days)s jours") % {
                "days": self.duration_days,
            }

        if self.duration_days < 30:
            weeks, remaining_days = divmod(self.duration_days, 7)

            if remaining_days:
                return _("%(weeks)s semaines et %(days)s jours") % {
                    "weeks": weeks,
                    "days": remaining_days,
                }

            return _("%(weeks)s semaines") % {
                "weeks": weeks,
            }

        months, remaining_days = divmod(self.duration_days, 30)

        if remaining_days:
            return _("%(months)s mois et %(days)s jours") % {
                "months": months,
                "days": remaining_days,
            }

        return _("%(months)s mois") % {
            "months": months,
        }

@property
def is_available(self) -> bool:
    return (
        self.status == OfferStatus.PUBLISHED
        and not self.is_deleted
        and self.available_positions > 0
        and self.application_deadline >= timezone.now()
    )
