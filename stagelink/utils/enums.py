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


class OTPType(models.TextChoices):
    SIGNUP = "SIGNUP", _("Inscription")
    PASSWORD_RESET = "PASSWORD_RESET", _("Réinitialisation du mot de passe")


class SalaryPeriod(models.TextChoices):
    DAY = "DAY", _("Jour")
    WEEK = "WEEK", _("Semaine")
    MONTH = "MONTH", _("Mois")


# Devises proposées pour la rémunération (XAF par défaut sur le modèle).
class SALARY_CURRENCY_CHOICES(models.TextChoices):
    ("XAF", _("Franc CFA (XAF)")),
    ("EUR", _("Euro (EUR)")),
    ("USD", _("Dollar américain (USD)")),



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

class NotificationType(models.TextChoices):
    APPLICATION = "application", _("Candidature")
    OFFER = "offer", _("Offre")
    SYSTEM = "system", _("Système")  


class DonationStatus(models.TextChoices):
    PENDING = "pending", _("En attente")
    COMPLETED = "completed", _("Effectué")
    FAILED = "failed", _("Échoué")
    CANCELLED = "cancelled", _("Annulé")


class PaymentStatus(models.TextChoices):
    PENDING = "pending", _("En attente")
    SUCCESS = "success", _("Réussi")
    FAILED = "failed", _("Échoué")
    CANCELLED = "cancelled", _("Annulé")
    REFUNDED = "refunded", _("Remboursé")
    PARTIALLY_REFUNDED = "partially_refunded", _("Partiellement remboursé")


class PaymentMethod(models.TextChoices):
    CARD = "card", _("Carte bancaire")
    MOBILE_MONEY = "mobile_money", _("Mobile Money")


class PaymentProvider(models.TextChoices):
    FLUTTERWAVE = "flutterwave", _("Flutterwave")
    STRIPE = "stripe", _("Stripe")     
