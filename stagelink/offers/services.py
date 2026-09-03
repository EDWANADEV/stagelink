from django.core.exceptions import ValidationError
from django.utils import timezone

from stagelink.utils.enums import OfferStatus

from .models import InternshipOffer
from .permissions import require_admin
from .permissions import require_company
from .permissions import require_offer_owner


# Champs qu'une entreprise ou un administrateur
# peut fournir lors de la création d'une offre.
OFFER_INPUT_FIELDS = (
    "title",
    "description",
    "domain",
    "required_skills",
    "education_level",
    "location",
    "duration_days",
    "start_date",
    "application_deadline",
    "salary",
    "salary_period",
    "available_positions",
    "application_mode",
    "application_url",
)

# Champs modifiables après création.
OFFER_EDITABLE_FIELDS = OFFER_INPUT_FIELDS


def _clean_offer_data(data: dict) -> dict:
    """
    Ne conserve que les champs autorisés pour une offre.

    Cela empêche notamment de modifier directement :
    - created_by
    - company
    - status
    - published_at
    - updated_by
    """
    return {
        field: data[field]
        for field in OFFER_INPUT_FIELDS
        if field in data
    }


def create_offer(user, data: dict) -> InternshipOffer:
    """
    Crée une offre appartenant à une entreprise.

    L'utilisateur doit être une entreprise.
    L'entreprise associée au profil de l'utilisateur
    est automatiquement utilisée.

    Le créateur est automatiquement enregistré dans
    BaseModel.created_by.
    """
    require_company(user)

    try:
        company_profile = user.company_profile
    except AttributeError as exc:
        raise ValidationError(
            "L'utilisateur ne possède pas encore de profil entreprise.",
        ) from exc

    offer_data = _clean_offer_data(data)

    offer = InternshipOffer(
        company=company_profile,
        created_by=user,
        **offer_data,
    )

    offer.full_clean()
    offer.save()

    return offer


def create_relayed_offer(user, data: dict) -> InternshipOffer:
    """
    Crée une offre relayée par l'administration.

    Seul un utilisateur disposant des droits d'administration
    (is_staff=True) peut créer ce type d'offre.

    Une offre relayée n'est pas liée à un CompanyProfile
    StageLink : company reste donc à None.

    L'administrateur qui crée l'offre devient son créateur
    via BaseModel.created_by.
    """
    require_admin(user)

    offer_data = _clean_offer_data(data)

    offer = InternshipOffer(
        company=None,
        created_by=user,
        **offer_data,
    )

    offer.full_clean()
    offer.save()

    return offer


def update_offer(
    user,
    offer: InternshipOffer,
    data: dict,
) -> InternshipOffer:
    """
    Modifie une offre.

    Seul le créateur de l'offre peut la modifier.

    Les champs sensibles comme :
    - company
    - created_by
    - status
    - published_at
    - updated_by

    ne peuvent pas être modifiés directement par data.
    """
    require_offer_owner(user, offer)

    if offer.is_deleted:
        raise ValidationError(
            "Une offre supprimée ne peut pas être modifiée.",
        )

    offer_data = _clean_offer_data(data)

    for field, value in offer_data.items():
        setattr(offer, field, value)

    offer.updated_by = user

    offer.full_clean()
    offer.save()

    return offer


def publish_offer(
    user,
    offer: InternshipOffer,
) -> InternshipOffer:
    """
    Publie une offre appartenant à l'utilisateur.

    L'offre doit être à l'état BROUILLON.
    """
    require_offer_owner(user, offer)

    if offer.is_deleted:
        raise ValidationError(
            "Une offre supprimée ne peut pas être publiée.",
        )

    if offer.status != OfferStatus.DRAFT:
        raise ValidationError(
            "Seules les offres en brouillon peuvent être publiées.",
        )

    offer.status = OfferStatus.PUBLISHED
    offer.published_at = timezone.now()
    offer.updated_by = user

    offer.full_clean()
    offer.save()

    return offer


def close_offer(
    user,
    offer: InternshipOffer,
) -> InternshipOffer:
    """
    Ferme une offre appartenant à l'utilisateur.

    Seule une offre actuellement publiée peut être fermée.
    """
    require_offer_owner(user, offer)

    if offer.is_deleted:
        raise ValidationError(
            "Une offre supprimée ne peut pas être fermée.",
        )

    if offer.status != OfferStatus.PUBLISHED:
        raise ValidationError(
            "Seules les offres publiées peuvent être fermées.",
        )

    offer.status = OfferStatus.CLOSED
    offer.updated_by = user

    offer.full_clean()
    offer.save()

    return offer


def delete_offer(
    user,
    offer: InternshipOffer,
) -> InternshipOffer:
    """
    Supprime logiquement une offre.

    L'offre n'est pas réellement supprimée de la base de données.
    BaseModel.soft_delete() met simplement is_deleted à True.
    """
    require_offer_owner(user, offer)

    if offer.is_deleted:
        raise ValidationError(
            "Cette offre est déjà supprimée.",
        )

    offer.soft_delete(user)

    return offer
