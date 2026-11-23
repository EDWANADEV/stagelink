from django.urls import path

from .views import OfferAssistantView

app_name = "ai_assistant"

urlpatterns = [
    path("offers/<uuid:offer_pk>/", OfferAssistantView.as_view(), name="offer"),
]
