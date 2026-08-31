from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    STUDENT = "STUDENT", _("Elève")
    COMPANY = "COMPANY", _("Entreprise")


class Language(models.TextChoices):
    FRENCH = "fr", _("Français")
    ENGLISH = "en", _("English")
    

class OfferStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Brouillon")
    PUBLISHED = "PUBLISHED", _("Publiée")
    CLOSED = "CLOSED", _("Fermée")


class SalaryPeriod(models.TextChoices):
    DAY = "DAY", _("Jour")
    WEEK = "WEEK", _("Semaine")
    MONTH = "MONTH", _("Mois")

class ApplicationMode(models.TextChoices):
    INTERNAL = "INTERNAL", _("Candidature sur StageLink")
    EXTERNAL = "EXTERNAL", _("Candidature externe")


class ApplicationStatus(models.TextChoices):
    RECEIVED = "received", _("Reçue")
    VIEWED = "viewed", _("Consultée")
    INTERVIEW = "interview", _("Entretien")
    ACCEPTED = "accepted", _("Acceptée")
    REJECTED = "rejected", _("Refusée")
    WITHDRAWN = "withdrawn", _("Retirée")

    
