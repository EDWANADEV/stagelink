from __future__ import annotations

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import (
    AuthenticationForm,
    ReadOnlyPasswordHashField,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from stagelink.core.forms import DesignSystemFormMixin
from stagelink.users.models import User
from stagelink.utils.enums import Role


class SignupForm(UserCreationForm):
    """
    Formulaire d'inscription utilisateur.

    L'utilisateur choisit son rôle via une interface visuelle.
    Le rôle Étudiant est sélectionné par défaut.
    """

    role = forms.ChoiceField(
    label=_("Type de compte"),
    choices=Role.choices,
    initial=Role.STUDENT,
    widget=forms.RadioSelect(
        attrs={
            "class": "peer sr-only",
        }
    ),
)

    email = forms.EmailField(
        label=_("Adresse e-mail"),
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": _("Votre adresse e-mail"),
            }
        ),
    )

    password1 = forms.CharField(
        label=_("Mot de passe"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": _("Votre mot de passe"),
            }
        ),
    )

    password2 = forms.CharField(
        label=_("Confirmation du mot de passe"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": _("Confirmez votre mot de passe"),
            }
        ),
    )

    class Meta:
        model = User
        fields = (
            "email",
            "role",
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                _("Un compte existe déjà avec cette adresse e-mail.")
            )

        return email


class SigninForm(DesignSystemFormMixin, AuthenticationForm):
    """
    Formulaire de connexion StageLink.

    L'adresse e-mail est utilisée comme identifiant.
    """

    username = forms.EmailField(
        label=_("Adresse e-mail"),
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": _("Votre adresse e-mail"),
            }
        ),
    )

    password = forms.CharField(
        label=_("Mot de passe"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": _("Votre mot de passe"),
            }
        ),
    )

    remember_me = forms.BooleanField(
        label=_("Se souvenir de moi"),
        required=False,
    )

    error_messages = {
        "invalid_login": _(
            "Adresse e-mail ou mot de passe incorrect."
        ),
        "inactive": _(
            "Ce compte est actuellement désactivé."
        ),
    }

    def clean(self):
        cleaned_data = super().clean()

        email = cleaned_data.get("username")
        password = cleaned_data.get("password")

        if email and password:
            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password,
            )

            if self.user_cache is None:
                raise self.get_invalid_login_error()

            self.confirm_login_allowed(self.user_cache)

        return cleaned_data


class OtpVerificationForm(forms.Form):
    """Formulaire de vérification d'un code OTP."""

    token = forms.CharField(
        widget=forms.HiddenInput(),
    )

    code = forms.CharField(
        label=_("Code de vérification"),
        max_length=6,
        min_length=6,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "maxlength": "6",
                "placeholder": "000000",
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data["code"]

        if not code.isdigit():
            raise ValidationError(
                _("Le code doit contenir uniquement des chiffres.")
            )

        return code


class ForgotPasswordForm(forms.Form):
    """Formulaire de demande de réinitialisation."""

    email = forms.EmailField(
        label=_("Adresse e-mail"),
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": _("Votre adresse e-mail"),
            }
        ),
    )


class PasswordResetConfirmForm(SetPasswordForm):
    """
    Formulaire permettant de définir un nouveau mot de passe.
    """

    token = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )

    new_password1 = forms.CharField(
        label=_("Nouveau mot de passe"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": _("Votre nouveau mot de passe"),
            }
        ),
    )

    new_password2 = forms.CharField(
        label=_("Confirmation du nouveau mot de passe"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": _(
                    "Confirmez votre nouveau mot de passe"
                ),
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)

        if user is None:
            # Le user sera défini par la vue après validation du token.
            user = User()

        super().__init__(user, *args, **kwargs)

        self.fields["password1"] = self.fields.pop("new_password1")
        self.fields["password2"] = self.fields.pop("new_password2")


class ChangePasswordForm(SetPasswordForm):
    """Formulaire de changement de mot de passe."""

    old_password = forms.CharField(
        label=_("Mot de passe actuel"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": _("Votre mot de passe actuel"),
            }
        ),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)

        self.fields["new_password1"].label = _(
            "Nouveau mot de passe"
        )
        self.fields["new_password2"].label = _(
            "Confirmation du nouveau mot de passe"
        )

    def clean_old_password(self):
        old_password = self.cleaned_data["old_password"]

        if not self.user.check_password(old_password):
            raise ValidationError(
                _("Votre mot de passe actuel est incorrect.")
            )

        return old_password


class UserAdminCreationForm(UserCreationForm):
    """Formulaire de création d'un utilisateur depuis l'admin."""

    class Meta:
        model = User
        fields = (
            "email",
            "name",
            "role",
            "is_active",
            "is_staff",
            "is_superuser",
        )


class UserAdminChangeForm(forms.ModelForm):
    """Formulaire de modification d'un utilisateur dans l'admin."""

    password = ReadOnlyPasswordHashField(
        label=_("Mot de passe"),
        help_text=_(
            "Les mots de passe sont stockés sous forme de hash. "
            "Pour modifier le mot de passe, utilisez le formulaire "
            "de changement de mot de passe."
        ),
    )

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "name",
            "role",
            "email_verified",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
        )
        