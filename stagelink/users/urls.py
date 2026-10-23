from django.urls import path

from stagelink.users.views.forgot_password_views import (
    ForgotPasswordView,
    ResetPasswordView,
)
from stagelink.users.views.login_views import (
    SigninView,
    UserLogoutView,
    UserRedirectView,
)
from stagelink.users.views.otp_views import (
    ResendOtpView,
    VerifyOtpView,
)
from stagelink.users.views.register_views import (
    SignupView,
)


app_name = "users"


urlpatterns = [
    # =========================
    # Authentication
    # =========================

    path(
        "signin/",
        SigninView.as_view(),
        name="signin",
    ),

    path(
        "signup/",
        SignupView.as_view(),
        name="signup",
    ),

    path(
        "logout/",
        UserLogoutView.as_view(),
        name="logout",
    ),

    # =========================
    # OTP
    # =========================

    path(
        "verify-otp/<str:purpose>/<str:token>/",
        VerifyOtpView.as_view(),
        name="verify_otp",
    ),

    path(
        "verify-otp/<str:purpose>/<str:token>/resend/",
        ResendOtpView.as_view(),
        name="resend_otp",
    ),

    # =========================
    # Password reset
    # =========================

    path(
        "forgot-password/",
        ForgotPasswordView.as_view(),
        name="forgot_password",
    ),

    path(
        "reset-password/<str:token>/",
        ResetPasswordView.as_view(),
        name="reset_password",
    ),

    # =========================
    # Post-authentication
    # =========================

    path(
        "~redirect/",
        UserRedirectView.as_view(),
        name="redirect",
    ),
]