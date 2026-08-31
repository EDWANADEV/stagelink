from django.contrib import admin

from django.contrib import admin

from .models import InternshipOffer


@admin.register(InternshipOffer)
class InternshipOfferAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "domain",
        "status",
        "application_mode",
        "application_deadline",
        "published_at",
    )

    list_filter = (
        "status",
        "application_mode",
        "domain",
    )

    search_fields = (
        "title",
        "description",
        "company__name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )
