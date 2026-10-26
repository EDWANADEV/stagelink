from urllib.parse import urlsplit

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView

from stagelink.core.permissions import CompanyRequiredMixin
from stagelink.core.permissions import get_profile
from stagelink.utils.enums import ApplicationMode
from stagelink.utils.enums import OfferStatus
from stagelink.utils.enums import Role

from .forms import OfferForm
from .forms import OfferSearchForm
from .models import InternshipOffer
from .services import close_offer
from .services import create_offer
from .services import publish_offer
from .services import update_offer

OFFERS_PER_PAGE = 12
COMPANY_OFFERS_PER_PAGE = 20


class WorkspaceLayoutMixin:
    """
    Affiche les pages publiques des offres dans l'espace de travail
    pour un utilisateur ayant terminé son parcours d'inscription,
    et dans la mise en page publique pour les visiteurs.
    """

    active_nav = "offers"

    def get_base_template(self) -> str:
        user = self.request.user

        if (
            user.is_authenticated
            and user.email_verified
            and get_profile(user) is not None
        ):
            return "dashboard/base.html"

        return "base.html"

    def get_context_data(self, **kwargs):
        kwargs.setdefault("base_template", self.get_base_template())
        return super().get_context_data(**kwargs)


class OfferListView(WorkspaceLayoutMixin, ListView):
    """Liste publique des offres disponibles, avec recherche et filtres."""

    template_name = "offers/offer_list.html"
    context_object_name = "offers"
    paginate_by = OFFERS_PER_PAGE

    def get_queryset(self):
        available = InternshipOffer.objects.available()
        domains = (
            available.order_by("domain")
            .values_list("domain", flat=True)
            .distinct()
        )
        self.search_form = OfferSearchForm(self.request.GET, domains=domains)

        return self.search_form.filter_queryset(
            available.select_related("company").order_by(
                *OfferSearchForm.SORT_ORDERING[OfferSearchForm.SORT_RECENT],
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = self.search_form
        context["is_filtered"] = any(
            self.request.GET.get(name)
            for name in ("q", "domain", "location", "application_mode")
        )
        return context


class OfferDetailView(WorkspaceLayoutMixin, DetailView):
    """
    Détail d'une offre.

    Les offres publiées ou fermées sont publiques ; un brouillon
    n'est visible que par l'entreprise qui l'a créé.
    """

    template_name = "offers/offer_detail.html"
    context_object_name = "offer"

    def get_queryset(self):
        queryset = InternshipOffer.objects.select_related("company")
        user = self.request.user

        # L'administration peut prévisualiser toutes les offres.
        if user.is_authenticated and user.is_staff:
            return queryset

        visible = Q(status__in=(OfferStatus.PUBLISHED, OfferStatus.CLOSED))

        if user.is_authenticated and user.role == Role.COMPANY:
            visible |= Q(created_by=user)

        return queryset.filter(visible)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        offer = self.object
        context["is_owner"] = (
            self.request.user.is_authenticated
            and offer.created_by_id == self.request.user.pk
        )
        return context


class OfferApplyRedirectView(View):
    """
    Redirige vers le site source d'une offre à candidature externe
    (notamment les offres relayées par l'administration).

    La redirection n'est faite que pour une offre disponible et vers
    une URL http(s) : la vue ne peut pas servir de redirection ouverte.
    """

    def get(self, request, pk):
        offer = get_object_or_404(
            InternshipOffer.objects.available(),
            pk=pk,
            application_mode=ApplicationMode.EXTERNAL,
        )

        if urlsplit(offer.application_url).scheme not in ("http", "https"):
            raise Http404

        return HttpResponseRedirect(offer.application_url)


class CompanyOfferMixin(CompanyRequiredMixin):
    """Restreint les vues aux offres de l'entreprise connectée."""

    active_nav = "company-offers"

    def get_queryset(self):
        return InternshipOffer.objects.filter(
            company=self.profile,
            created_by=self.request.user,
        )


class CompanyOfferListView(CompanyOfferMixin, ListView):
    template_name = "offers/company_offer_list.html"
    context_object_name = "offers"
    paginate_by = COMPANY_OFFERS_PER_PAGE

    def get_queryset(self):
        queryset = super().get_queryset().order_by("-created_at")
        self.status_filter = self.request.GET.get("status", "")

        if self.status_filter in OfferStatus.values:
            queryset = queryset.filter(status=self.status_filter)
        else:
            self.status_filter = ""

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_filter"] = self.status_filter
        context["status_choices"] = OfferStatus.choices
        return context


class OfferFormMixin:
    """Transmet la saisie aux services métier et affiche leurs erreurs."""

    form_class = OfferForm
    template_name = "offers/offer_form.html"

    def save_offer(self, form):
        raise NotImplementedError

    def form_valid(self, form):
        try:
            self.object = self.save_offer(form)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)

        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("offers:detail", kwargs={"pk": self.object.pk})


class OfferCreateView(CompanyOfferMixin, OfferFormMixin, CreateView):
    success_message = _(
        "Votre offre a été enregistrée en brouillon. "
        "Relisez-la puis publiez-la pour la rendre visible.",
    )

    def save_offer(self, form):
        return create_offer(self.request.user, form.cleaned_data)


class OfferUpdateView(CompanyOfferMixin, OfferFormMixin, UpdateView):
    success_message = _("Votre offre a été mise à jour.")

    def get_queryset(self):
        # Une offre fermée n'est plus modifiable.
        return super().get_queryset().exclude(status=OfferStatus.CLOSED)

    def save_offer(self, form):
        # form.instance porte déjà la saisie : on repart de l'état en base
        # pour que le service applique lui-même les champs autorisés.
        offer = self.get_object()
        return update_offer(self.request.user, offer, form.cleaned_data)


class OfferStatusChangeView(CompanyOfferMixin, View):
    """Action de changement de statut (POST uniquement)."""

    http_method_names = ["post"]
    service = None  # fonction de service : (user, offer) -> offer
    success_message = ""

    def post(self, request, pk):
        offer = get_object_or_404(self.get_queryset(), pk=pk)

        try:
            self.service(request.user, offer)
        except ValidationError as exc:
            for message in exc.messages:
                messages.error(request, message)
        else:
            messages.success(request, self.success_message)

        return redirect("offers:detail", pk=offer.pk)


class OfferPublishView(OfferStatusChangeView):
    service = staticmethod(publish_offer)
    success_message = _("Votre offre est publiée et visible par les étudiants.")


class OfferCloseView(OfferStatusChangeView):
    service = staticmethod(close_offer)
    success_message = _("Votre offre est fermée : elle n'accepte plus de candidatures.")


offer_list_view = OfferListView.as_view()
offer_detail_view = OfferDetailView.as_view()
offer_apply_redirect_view = OfferApplyRedirectView.as_view()
company_offer_list_view = CompanyOfferListView.as_view()
offer_create_view = OfferCreateView.as_view()
offer_update_view = OfferUpdateView.as_view()
offer_publish_view = OfferPublishView.as_view()
offer_close_view = OfferCloseView.as_view()
