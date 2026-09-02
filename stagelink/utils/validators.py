from io import BytesIO
import phonenumbers

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from PIL import Image
from pypdf import PdfReader

def normalize_phone_number(value:str) -> str:
    if not value:
        return value
    try:
        parsed = phonenumbers.parse(value, "CM") # Cameroun par défaut si non préfixé
        if not phonenumbers.is_valid_number(parsed):
            raise ValidationError(_("Numéro de téléphone international invalide."))
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException as e:
        raise ValidationError(_("Numéro de téléphone international invalide.")) from e

def validate_phone_number(value: str) -> None:
    if value:
        normalize_phone_number(value)


def validate_cv(file) -> None:
    """Valide l'extension, le format réel et la taille du CV."""
    extension = file.name.rsplit(".", 1)[-1].lower()

    if extension != "pdf":
        raise ValidationError(
            _("Le CV doit être au format PDF."),
        )

    max_size = settings.MAX_CV_SIZE_MB * 1024 * 1024

    if file.size > max_size:
        raise ValidationError(
            _(
                "La taille du CV ne doit pas dépasser "
                "%(max_size)s Mo."
            ),
            params={
                "max_size": settings.MAX_CV_SIZE_MB,
            },
        )

    try:
        file.seek(0)
        PdfReader(file)
    except Exception as exc:
        raise ValidationError(
            _("Le fichier envoyé n'est pas un PDF valide."),
        ) from exc
    finally:
        file.seek(0)


def validate_company_logo(file) -> None:
    """Valide l'extension, le format réel et la taille du logo."""
    extension = file.name.rsplit(".", 1)[-1].lower()

    allowed_extensions = {
        "jpg",
        "jpeg",
        "png",
    }

    if extension not in allowed_extensions:
        raise ValidationError(
            _("Le logo doit être au format JPEG ou PNG."),
        )

    max_size = settings.MAX_COMPANY_LOGO_SIZE_MB * 1024 * 1024

    if file.size > max_size:
        raise ValidationError(
            _(
                "La taille du logo ne doit pas dépasser "
                "%(max_size)s Mo."
            ),
            params={
                "max_size": settings.MAX_COMPANY_LOGO_SIZE_MB,
            },
        )

    try:
        file.seek(0)

        with Image.open(BytesIO(file.read())) as image:
            image.verify()

    except Exception as exc:
        raise ValidationError(
            _("Le fichier envoyé n'est pas une image valide."),
        ) from exc

    finally:
        file.seek(0)
