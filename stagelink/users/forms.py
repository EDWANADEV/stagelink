from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth import forms as admin_forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.password_validation import validate_password
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _

from .models import User
from .models import UserProfile


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):
        model = User
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.AdminUserCreationForm):
    """
    Form for User Creation in the Admin Area.
    """

    class Meta(admin_forms.UserCreationForm.Meta):
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(UserCreationForm):
    """
    Standard signup form based on UserCreationForm.
    Django automatically detects USERNAME_FIELD (email) and adapts the fields.
    """

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "password1", "password2")


class SigninForm(forms.Form):
    email = forms.EmailField(label=_("Adresse e-mail"))
    password = forms.CharField(label=_("Mot de passe"), strip=False, widget=forms.PasswordInput)
    remember_me = forms.BooleanField(label=_("Rester connecté"), required=False)

    user = None

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")
        if not email or not password:
            return cleaned_data

        self.user = authenticate(email=email, password=password)
        if self.user is None:
            raise forms.ValidationError(_("Adresse e-mail ou mot de passe incorrect."))
        if not self.user.is_active:
            raise forms.ValidationError(_("Ce compte est désactivé."))
        return cleaned_data


class SignupForm(forms.ModelForm):
    password1 = forms.CharField(label=_("Mot de passe"), strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Confirmation du mot de passe"), strip=False, widget=forms.PasswordInput)
    accept_terms = forms.BooleanField(label=_("Conditions d'utilisation"), required=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password1", "password2", "accept_terms")

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Un compte existe déjà avec cette adresse e-mail."))
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", _("Les mots de passe ne correspondent pas."))
        if password1:
            try:
                validate_password(password1)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data

    def save(self, *, commit=True):
        user = super().save(commit=False)
        user.email = user.email.lower().strip()
        user.username = None
        user.is_verified = False
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(label=_("Adresse e-mail"))

    def clean_email(self):
        return self.cleaned_data["email"].lower().strip()


class OtpVerificationForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)
    code = forms.CharField(label=_("Code OTP"), min_length=6, max_length=6)

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError(_("Entrez le code à 6 chiffres reçu par e-mail."))
        return code


class PasswordResetConfirmForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)
    password1 = forms.CharField(label=_("Nouveau mot de passe"), strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Confirmation du mot de passe"), strip=False, widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", _("Les mots de passe ne correspondent pas."))
        if password1:
            try:
                validate_password(password1)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data


# ── Profil utilisateur ────────────────────────────────────────────────────────


# class ProfileForm(forms.ModelForm):
#     """Édition des informations personnelles de l'utilisateur (modèle User)."""

#     biography = forms.CharField(
#         label=_("Biographie"),
#         max_length=500,
#         required=False,
#         widget=forms.Textarea,
#     )

#     class Meta:
#         model = User
#         fields = (
#             "first_name",
#             "last_name",
#             "email",
#             "phone_number",
#             "job_title",
#             "biography",
#             "date_of_birth",
#             "language",
#         )
#         widgets = {
#             "date_of_birth": forms.DateInput(
#                 format="%Y-%m-%d",
#                 attrs={"type": "date"},
#             ),
#         }

#     def __init__(self, *args, profile=None, **kwargs):
#         self.profile = profile
#         super().__init__(*args, **kwargs)
#         # L'adresse e-mail est immuable : non modifiable côté formulaire.
#         self.fields["email"].disabled = True
#         if self.profile is None and self.instance.pk:
#             self.profile = UserProfile.objects.filter(user=self.instance).first()
#         if self.profile is not None:
#             self.fields["biography"].initial = self.profile.biography

#     def clean_email(self):
#         email = self.cleaned_data["email"].lower().strip()
#         if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
#             raise forms.ValidationError(_("Un compte existe déjà avec cette adresse e-mail."))
#         return email

#     def save(self, commit=True):  # noqa: FBT002
#         # Garde de sécurité : l'adresse e-mail est immuable. On force sa valeur
#         # d'origine quelle que soit la donnée soumise (ceinture + bretelles).
#         original_email = self.instance.email
#         user = super().save(commit=False)
#         user.email = original_email
#         if commit:
#             user.save()
#             profile = self.profile or UserProfile.objects.create(user=user)
#             profile.biography = self.cleaned_data["biography"]
#             profile.save(update_fields=["biography", "updated_at"])
#         return user


# class ProfileSocialForm(forms.ModelForm):
#     """Édition des liens sociaux et de l'adresse (modèle UserProfile)."""

#     class Meta:
#         model = UserProfile
#         fields = (
#             "linkedin_url",
#             "facebook_url",
#             "twitter_url",
#             "instagram_url",
#             "country",
#             "city",
#             "postal_code",
#         )


# class ChangePasswordForm(forms.Form):
#     """Changement de mot de passe depuis le profil (avec vérification de l'actuel)."""

#     current_password = forms.CharField(
#         label=_("Mot de passe actuel"),
#         strip=False,
#         widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
#     )
#     new_password1 = forms.CharField(
#         label=_("Nouveau mot de passe"),
#         strip=False,
#         widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
#     )
#     new_password2 = forms.CharField(
#         label=_("Confirmation du nouveau mot de passe"),
#         strip=False,
#         widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
#     )

#     def __init__(self, user=None, *args, **kwargs):
#         self.user = user
#         super().__init__(*args, **kwargs)

#     def clean_current_password(self):
#         current_password = self.cleaned_data["current_password"]
#         if self.user is not None and not self.user.check_password(current_password):
#             raise forms.ValidationError(_("Le mot de passe actuel est incorrect."))
#         return current_password

#     def clean(self):
#         cleaned_data = super().clean()
#         password1 = cleaned_data.get("new_password1")
#         password2 = cleaned_data.get("new_password2")
#         if password1 and password2 and password1 != password2:
#             self.add_error("new_password2", _("Les mots de passe ne correspondent pas."))
#         if password1:
#             try:
#                 validate_password(password1, user=self.user)
#             except forms.ValidationError as error:
#                 self.add_error("new_password1", error)
#         return cleaned_data


# class AvatarUploadForm(forms.Form):
#     """Téléversement de la photo de profil."""

#     avatar = forms.ImageField(label=_("Photo de profil"))