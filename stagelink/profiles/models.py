from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from stagelink.core.models import BaseModel
from stagelink.utils.validators import validate_cv
from stagelink.utils.validators import validate_company_logo
from stagelink.utils.validators import validate_phone_number
from stagelink.utils.enums import Language


class StudentProfile(BaseModel):
    """
    Profile containing information specific to a StageLink student.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
        verbose_name=_("Utilisateur"),
    )

    field_of_study = models.CharField(
        _("Domaine d'étude"),
        max_length=150,
    )

    level = models.CharField(
        _("Niveau d'étude"),
        max_length=100,
    )

    skills = models.JSONField(
        _("Compétences"),
        default=list,
        blank=True,
    )

    language = models.CharField(
        _("Langue"),
        max_length=2,
        choices=Language.choices,
        default=Language.FRENCH,
    )

    cv = models.FileField(
        _("CV"),
        upload_to="cv/",
        validators=[validate_cv],
        help_text=_(
        "Format PDF uniquement, taille maximale de 20 Mo."
            ),
        blank=True,
    )

    class Meta:
        verbose_name = _("Profil étudiant")
        verbose_name_plural = _("Profils étudiants")

    def __str__(self) -> str:
        return self.user.name or self.user.email



class CompanyProfile(BaseModel):
    """
    Profil d'une entreprise présente sur StageLink.

    Les informations d'authentification restent dans User.
    Ce modèle contient uniquement les informations propres à l'entreprise.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_profile",
        verbose_name=_("Utilisateur"),
    )

    company_name = models.CharField(
        _("Nom de l'entreprise"),
        max_length=255,
    )

    description = models.TextField(
        _("Description"),
        blank=True,
    )

    phone_number = models.CharField(
        _("Numéro de téléphone"),
        max_length=16,
        validators=[validate_phone_number],
        blank=True,
    )

    address = models.CharField(
        _("Adresse"),
        max_length=255,
    )

    website = models.URLField(
        _("Site web"),
        blank=True,
    )

    logo = models.ImageField(
        _("Logo"),
        upload_to="profiles/company/logos/",
        blank=True,
        validators=[validate_company_logo],
        help_text=_(
            "Formats JPEG ou PNG, taille maximale de 10 Mo."
        ),
    )

    class Meta:
        verbose_name = _("Profil entreprise")
        verbose_name_plural = _("Profils entreprise")

    def __str__(self) -> str:
        return self.company_name