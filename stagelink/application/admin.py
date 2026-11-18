from django.contrib import admin

from .models import Application
from .models import ApplicationStatusHistory


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "offer",
        "status",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "student__user__email",
        "student__user__name",
        "offer__title",
        "offer__company__company_name",
    )

    readonly_fields = (
        "id",
        "status",
        "interview_at",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )

    ordering = ("-created_at",)


@admin.register(ApplicationStatusHistory)
class ApplicationStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "previous_status",
        "new_status",
        "changed_by",
        "created_at",
    )
    list_filter = ("new_status", "created_at")
    search_fields = (
        "application__student__user__email",
        "application__student__user__name",
        "application__offer__title",
    )
    readonly_fields = (
        "application",
        "previous_status",
        "new_status",
        "changed_by",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
