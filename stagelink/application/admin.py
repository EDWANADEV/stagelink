from django.contrib import admin

from .models import Application


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
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )

    ordering = ("-created_at",)

