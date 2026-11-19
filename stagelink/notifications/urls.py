from django.urls import path

from stagelink.notifications.views import NotificationListView
from stagelink.notifications.views import NotificationReadView

app_name = "notifications"

urlpatterns = [
    path("", NotificationListView.as_view(), name="list"),
    path("<uuid:pk>/read/", NotificationReadView.as_view(), name="read"),
]
