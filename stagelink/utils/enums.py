from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    STUDENT = "STUDENT", _("Elève")
    COMPANY = "COMPANY", _("Entreprise")


class OfferStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Brouillon")
    PUBLISHED = "PUBLISHED", _("Publiée")
    CLOSED = "CLOSED", _("Fermée")
