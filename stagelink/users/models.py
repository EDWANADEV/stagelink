
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db.models import EmailField
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel
from .managers import UserManager

from utils.enums import Role

    
class User(AbstractUser):
    """
    Default custom user model for StageLink.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]
    role = CharField(
        _("Role"),
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    email_verified = models.BooleanField(
        _("Adresse e-mail vérifiée"),
        default=False,
    )
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects: ClassVar[UserManager] = UserManager()

    def get_absolute_url(self) -> str:
        return reverse("users:detail", kwargs={"pk": self.id})
    
    
class OTPVerification(BaseModel):
    class OTPType(models.TextChoices):
        SIGNUP = "SIGNUP", _("Inscription")
        PASSWORD_RESET = "PASSWORD_RESET", _("Réinitialisation du mot de passe")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="otp_verifications",
    )
    code = models.CharField(
        _("Code OTP"),
        max_length=6,
    )
    otp_type = models.CharField(
        _("Type de vérification"),
        max_length=20,
        choices=OTPType.choices,
    )
    expires_at = models.DateTimeField(
        _("Date d'expiration"),
    )
    is_used = models.BooleanField(
        _("Utilisé"),
        default=False,
    )
    attempts = models.PositiveIntegerField(
        _("Nombre de tentatives"),
        default=0,
    )
    

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Vérification OTP")
        verbose_name_plural = _("Vérifications OTP")

    def __str__(self) -> str:
        return f"{self.user.email} - {self.otp_type}"
    
