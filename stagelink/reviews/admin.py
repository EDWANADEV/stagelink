from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Review

SHORT_COMMENT_LENGTH = 50


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "rating",
        "short_comment",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "rating",
        "created_at",
    )

    search_fields = (
        "user__email",
        "user__name",
        "comment",
    )

    readonly_fields = (
        "user",
        "rating",
        "comment",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "is_deleted",
    )

    list_select_related = ("user",)

    def short_comment(self, obj):
        if not obj.comment:
            return "—"

        return (
            obj.comment[:SHORT_COMMENT_LENGTH] + "..."
            if len(obj.comment) > SHORT_COMMENT_LENGTH
            else obj.comment
        )

    short_comment.short_description = _("Commentaire")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
