from django.contrib import admin
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Review

SHORT_COMMENT_LENGTH = 50


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    actions = ("approve_reviews",)

    list_display = (
        "user",
        "rating",
        "short_comment",
        "is_approved",
        "approved_at",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "rating",
        "is_approved",
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
        "is_approved",
        "approved_at",
        "approved_by",
    )

    list_select_related = ("user",)

    @admin.action(description=_("Approuver les avis sélectionnés pour publication"))
    def approve_reviews(self, request, queryset):
        approved_at = timezone.now()
        approved_count = 0
        with transaction.atomic():
            for review in queryset.select_for_update():
                if review.is_approved or review.is_deleted:
                    continue
                review.is_approved = True
                review.approved_at = approved_at
                review.approved_by = request.user
                review.updated_by = request.user
                review.save(
                    update_fields=(
                        "is_approved",
                        "approved_at",
                        "approved_by",
                        "updated_by",
                        "updated_at",
                    ),
                )
                approved_count += 1
        self.message_user(
            request,
            _("%(count)s avis approuvé(s) pour publication.") % {
                "count": approved_count,
            },
            level="success",
        )

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
