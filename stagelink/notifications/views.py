from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import ListView

from stagelink.notifications.models import Notification
from stagelink.notifications.services import NotificationService


class NotificationListView(LoginRequiredMixin, ListView):
    login_url = "users:signin"
    template_name = "notifications/list.html"
    context_object_name = "notifications"
    paginate_by = 30

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by(
            "-created_at",
        )


class NotificationReadView(LoginRequiredMixin, View):
    login_url = "users:signin"
    http_method_names = ["post"]

    def post(self, request, pk):
        notification = get_object_or_404(
            Notification.objects.filter(user=request.user),
            pk=pk,
        )
        NotificationService.mark_as_read(notification, request.user)
        return redirect("notifications:list")
