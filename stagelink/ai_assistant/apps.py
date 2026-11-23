from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AIAssistantConfig(AppConfig):
    name = "stagelink.ai_assistant"
    verbose_name = _("Assistance facultative")
