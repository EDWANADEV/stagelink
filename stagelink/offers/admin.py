from django import forms
from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from stagelink.utils.enums import ApplicationMode
from stagelink.utils.enums import OfferStatus

from .models import InternshipOffer


class RelayedOfferFilter(admin.SimpleListFilter):
    title = _("Origine")
    parameter_name = "origin"

    def lookups(self, request, model_admin):
        return (
            ("relayed", _("Relayée par l'administration")),
            ("company", _("Publiée par une entreprise")),
        )

    def queryset(self, request, queryset):
        if self.value() == "relayed":
            return queryset.filter(company__isnull=True)

        if self.value() == "company":
            return queryset.filter(company__isnull=False)

        return queryset


class InternshipOfferAdminForm(forms.ModelForm):
    class Meta:
        model = InternshipOffer
        fields = "__all__"  # noqa: DJ007

    def clean(self):
        cleaned_data = super().clean()

        # Une offre relayée n'a pas d'entreprise StageLink pour traiter
        # les candidatures : l'étudiant doit être redirigé vers la source.
        if (
            not cleaned_data.get("company")
            and cleaned_data.get("application_mode") != ApplicationMode.EXTERNAL
        ):
            self.add_error(
                "application_mode",
                _(
                    "Une offre relayée (sans entreprise) doit utiliser une "
                    "candidature externe vers son site source.",
                ),
            )

        return cleaned_data


@admin.register(InternshipOffer)
class InternshipOfferAdmin(admin.ModelAdmin):
    form = InternshipOfferAdminForm

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
        RelayedOfferFilter,
        "status",
        "application_mode",
        "domain",
    )

    list_select_related = ("company",)

    search_fields = (
        "title",
        "description",
        "company__company_name",
    )

    readonly_fields = (
        "published_at",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    )

    exclude = ("is_deleted",)

    actions = ("publish_selected", "close_selected")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user

        if obj.status == OfferStatus.PUBLISHED and obj.published_at is None:
            obj.published_at = timezone.now()

        super().save_model(request, obj, form, change)

    @admin.action(description=_("Publier les offres sélectionnées"))
    def publish_selected(self, request, queryset):
        offers = queryset.filter(
            status=OfferStatus.DRAFT,
            application_deadline__gt=timezone.now(),
        )
        count = offers.update(
            status=OfferStatus.PUBLISHED,
            published_at=timezone.now(),
            updated_by=request.user,
            updated_at=timezone.now(),
        )
        self.message_user(
            request,
            ngettext(
                "%(count)d offre publiée (seuls les brouillons non expirés "
                "sont publiés).",
                "%(count)d offres publiées (seuls les brouillons non expirés "
                "sont publiés).",
                count,
            )
            % {"count": count},
            messages.SUCCESS,
        )

    @admin.action(description=_("Fermer les offres sélectionnées"))
    def close_selected(self, request, queryset):
        count = queryset.filter(status=OfferStatus.PUBLISHED).update(
            status=OfferStatus.CLOSED,
            updated_by=request.user,
            updated_at=timezone.now(),
        )
        self.message_user(
            request,
            ngettext(
                "%(count)d offre fermée.",
                "%(count)d offres fermées.",
                count,
            )
            % {"count": count},
            messages.SUCCESS,
        )
