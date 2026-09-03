from django.apps import AppConfig

from django.utils.translation import gettext_lazy as _

class PaymentsConfig(AppConfig):
    name = 'stagelink.payments'
    verbose_name = _("Paiements")
