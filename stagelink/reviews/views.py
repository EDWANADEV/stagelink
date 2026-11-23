from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView
from django.views.generic import ListView
from django.views.generic import UpdateView

from .forms import ReviewForm
from .models import Review
from .services import ReviewService

REVIEWS_PER_PAGE = 10


class PublishedReviewsView(ListView):
    """List only reviews explicitly approved for publication."""

    template_name = "reviews/list.html"
    context_object_name = "reviews"
    paginate_by = REVIEWS_PER_PAGE

    def get_queryset(self):
        return (
            Review.objects.filter(is_approved=True)
            .only(
                "id",
                "rating",
                "comment",
                "created_at",
                "approved_at",
            )
            .order_by("-approved_at", "-pk")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["review_max_rating"] = settings.REVIEW_MAX_RATING
        return context


class MyReviewsView(LoginRequiredMixin, ListView):
    """Show only the signed-in user's review history and actions."""

    template_name = "reviews/my_reviews.html"
    context_object_name = "reviews"
    paginate_by = REVIEWS_PER_PAGE

    def get_queryset(self):
        return Review.all_objects.filter(user=self.request.user).order_by(
            "-created_at",
            "-pk",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["review_max_rating"] = settings.REVIEW_MAX_RATING
        context["active_review"] = Review.objects.filter(
            user=self.request.user,
        ).first()
        context["review_form"] = ReviewForm()
        return context


class ReviewCreateView(LoginRequiredMixin, CreateView):
    form_class = ReviewForm
    template_name = "reviews/review_form.html"
    success_url = reverse_lazy("reviews:mine")
    login_url = "users:signin"

    def form_valid(self, form):
        try:
            ReviewService.create_review(
                user=self.request.user,
                rating=form.cleaned_data["rating"],
                comment=form.cleaned_data["comment"],
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        messages.success(
            self.request,
            _("Votre avis a été reçu et attend la modération avant publication."),
        )
        return redirect("reviews:mine")

    def form_invalid(self, form):
        messages.error(self.request, _("Vérifiez les informations de votre avis."))
        return super().form_invalid(form)


class ReviewUpdateView(LoginRequiredMixin, UpdateView):
    form_class = ReviewForm
    template_name = "reviews/review_form.html"
    success_url = reverse_lazy("reviews:mine")
    login_url = "users:signin"

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user)

    def form_valid(self, form):
        try:
            ReviewService.update_review(
                user=self.request.user,
                review=self.object,
                rating=form.cleaned_data["rating"],
                comment=form.cleaned_data["comment"],
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)

        messages.success(
            self.request,
            _("Votre avis a été modifié et repasse en attente de modération."),
        )
        return redirect("reviews:mine")

    def form_invalid(self, form):
        messages.error(self.request, _("Vérifiez les informations de votre avis."))
        return super().form_invalid(form)


class ReviewDeleteView(LoginRequiredMixin, View):
    http_method_names = ["get", "post"]
    login_url = "users:signin"

    def get_review(self, request, pk):
        return get_object_or_404(
            Review.objects.filter(user=request.user),
            pk=pk,
        )

    def get(self, request, pk):
        return render(
            request,
            "reviews/review_confirm_delete.html",
            {"review": self.get_review(request, pk)},
        )

    def post(self, request, pk):
        review = self.get_review(request, pk)
        try:
            ReviewService.delete_review(user=request.user, review=review)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, _("Votre avis sur StageLink a été supprimé."))
        return redirect("reviews:mine")
