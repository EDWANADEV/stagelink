from django.urls import path

from .views import MyReviewsView
from .views import PublishedReviewsView
from .views import ReviewCreateView
from .views import ReviewDeleteView
from .views import ReviewUpdateView

app_name = "reviews"

urlpatterns = [
    path("", PublishedReviewsView.as_view(), name="list"),
    path("mine/", MyReviewsView.as_view(), name="mine"),
    path("create/", ReviewCreateView.as_view(), name="create"),
    path("<uuid:pk>/edit/", ReviewUpdateView.as_view(), name="update"),
    path("<uuid:pk>/delete/", ReviewDeleteView.as_view(), name="delete"),
]
