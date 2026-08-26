from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm

from django import forms
from django.contrib.auth import forms as admin_forms
from django.contrib.auth import authenticate
from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _

from .models import User
from .models import Role




class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.AdminUserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm and UserSocialSignupForm.
    """

    class Meta(admin_forms.UserCreationForm.Meta):
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """



class LoginForm(forms.Form):
    email = forms.EmailField(
        label=_("Adresse e-mail"),
        required=True,
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": _("exemple@email.com"),
                "class": (
                    "mt-2 block w-full rounded-[10px] border "
                    "border-[#D6DCE6] bg-white px-4 py-3 "
                    "text-[#16203A] shadow-sm outline-none "
                    "transition placeholder:text-[#8A94A6] "
                    "focus:border-[#1565C0] focus:ring-2 "
                    "focus:ring-[#1565C0]/20"
                ),
            },
        ),
    )

    password = forms.CharField(
        label=_("Mot de passe"),
        required=True,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": _("Votre mot de passe"),
                "class": (
                    "mt-2 block w-full rounded-[10px] border "
                    "border-[#D6DCE6] bg-white px-4 py-3 "
                    "text-[#16203A] shadow-sm outline-none "
                    "transition placeholder:text-[#8A94A6] "
                    "focus:border-[#1565C0] focus:ring-2 "
                    "focus:ring-[#1565C0]/20"
                ),
            },
        ),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if not User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                _("Aucun compte n'est associé à cette adresse e-mail.")
            )

        return email

    def clean(self):
        cleaned_data = super().clean()

        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if not email or not password:
            return cleaned_data

        self.user_cache = authenticate(
            self.request,
            username=email,
            password=password,
        )

        if self.user_cache is None:
            raise forms.ValidationError(
                _("L'adresse e-mail ou le mot de passe est incorrect.")
            )

        if not self.user_cache.is_active:
            raise forms.ValidationError(
                _("Ce compte est actuellement désactivé.")
            )

        return cleaned_data

    def get_user(self):
        return self.user_cache
    

class UserSignupForm(forms.Form):
    role = forms.ChoiceField(
        label=_("Je suis"),
        choices=Role.choices,
        widget=forms.RadioSelect,
        required=True,
    )

    email = forms.EmailField(
        label=_("Adresse e-mail"),
        required=True,
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": _("exemple@email.com"),
            }
        ),
    )

    password = forms.CharField(
        label=_("Mot de passe"),
        required=True,
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": _("Votre mot de passe"),
            }
        ),
    )

    password_confirmation = forms.CharField(
        label=_("Confirmer le mot de passe"),
        required=True,
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": _("Confirmez votre mot de passe"),
            }
        ),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                _("Cette adresse e-mail est déjà utilisée.")
            )

        return email

    def clean_password(self):
        password = self.cleaned_data["password"]

        password_validation.validate_password(password)

        return password

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        password_confirmation = cleaned_data.get("password_confirmation")

        if (
            password
            and password_confirmation
            and password != password_confirmation
        ):
            self.add_error(
                "password_confirmation",
                _("Les deux mots de passe ne correspondent pas."),
            )

        return cleaned_data



class OTPVerificationForm(forms.Form):
    code = forms.CharField(
        label=_("Code de vérification"),
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "maxlength": "6",
                "placeholder": "000000",
            },
        ),
    )
