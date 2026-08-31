from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class ApplicationConfig(AppConfig):
    name = 'stagelink.application'
    verbose_name= _("Candidature")
