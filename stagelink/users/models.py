
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db.models import EmailField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .managers import UserManager
from django.db import models


class Role(models.TextChoices):
    STUDENT = "STUDENT", _("Student")
    COMPANY = "COMPANY", _("Company")
    
    
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
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects: ClassVar[UserManager] = UserManager()

    def get_absolute_url(self) -> str:
        return reverse("users:detail", kwargs={"pk": self.id})
    
