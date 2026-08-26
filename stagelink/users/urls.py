from django.urls import path

from .views import user_detail_view
from .views import user_redirect_view
from .views import user_update_view
from .views import login_view
from .views import signup_view
from .views import verify_email_view
from .views import logout_view

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("<int:pk>/", view=user_detail_view, name="detail"),
    path("login/", view=login_view, name="login"),
    path("singup/", view=signup_view, name="signup"),
    path("verify-email/",view=verify_email_view, name="verify-email"),
    path( "logout/", view=logout_view, name="logout", ),
 
]
