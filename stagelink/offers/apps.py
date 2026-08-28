from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class OffersConfig(AppConfig):
    name = "stagelink.offers"
    verbose_name = _("Offres de stage")
