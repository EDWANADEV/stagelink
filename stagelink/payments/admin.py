from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "donation",
        "amount",
        "refunded_amount",
        "method",
        "provider",
        "status",
        "processed_at",
        "created_at",
    )

    list_filter = (
        "status",
        "method",
        "provider",
        "created_at",
    )

    search_fields = (
        "provider_payment_id",
        "donation__donor__email",
        "donation__donor__name",
    )

    readonly_fields = (
        "donation",
        "amount",
        "refunded_amount",
        "status",
        "method",
        "provider",
        "provider_payment_id",
        "provider_response",
        "metadata",
        "processed_at",
        "failure_reason",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "is_deleted",
    )

    list_select_related = (
        "donation",
        "donation__donor",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
