from django.urls import path

from .views import company_offer_list_view
from .views import offer_apply_redirect_view
from .views import offer_close_view
from .views import offer_create_view
from .views import offer_detail_view
from .views import offer_list_view
from .views import offer_publish_view
from .views import offer_update_view

app_name = "offers"
urlpatterns = [
    path("", view=offer_list_view, name="list"),
    path("mine/", view=company_offer_list_view, name="company-list"),
    path("new/", view=offer_create_view, name="create"),
    path("<uuid:pk>/", view=offer_detail_view, name="detail"),
    path("<uuid:pk>/edit/", view=offer_update_view, name="update"),
    path("<uuid:pk>/publish/", view=offer_publish_view, name="publish"),
    path("<uuid:pk>/close/", view=offer_close_view, name="close"),
    path("<uuid:pk>/apply/", view=offer_apply_redirect_view, name="apply-external"),
]
