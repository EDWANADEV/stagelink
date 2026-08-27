from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    STUDENT = "STUDENT", _("Student")
    COMPANY = "COMPANY", _("Company")
