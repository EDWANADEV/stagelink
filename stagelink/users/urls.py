from django.urls import path

from stagelink.users.views.forgot_password_views import ForgotPasswordView
from stagelink.users.views.forgot_password_views import ResetPasswordView
from stagelink.users.views.login_views import SigninView
from stagelink.users.views.login_views import UserLogoutView
from stagelink.users.views.login_views import UserRedirectView
from stagelink.users.views.otp_views import ResendOtpView
from stagelink.users.views.otp_views import VerifyOtpView
from stagelink.users.views.register_views import SignupView

app_name = "users"

urlpatterns = [
    path("signin/", SigninView.as_view(), name="signin"),
    path("login/", SigninView.as_view(), name="account_login"),
    path("logout/", UserLogoutView.as_view(), name="logout"),
    path("signup/", SignupView.as_view(), name="signup"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("verify-otp/<str:purpose>/<str:token>/", VerifyOtpView.as_view(), name="verify_otp"),
    path("verify-otp/<str:purpose>/<str:token>/resend/", ResendOtpView.as_view(), name="resend_otp"),
    path("reset-password/<str:token>/", ResetPasswordView.as_view(), name="reset_password"),
    path("~redirect/", UserRedirectView.as_view(), name="redirect"),
]