from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class ReviewsConfig(AppConfig):
    name = 'stagelink.reviews'
    verbose_name= _("Avis")
