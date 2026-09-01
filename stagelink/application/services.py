from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from stagelink.application.models import Application
from stagelink.offers.models import InternshipOffer
from stagelink.profiles.models import StudentProfile
from stagelink.utils.enums import ApplicationStatus


class ApplicationService:
    """Services métier liés aux candidatures."""

    # Transitions autorisées selon le diagramme d'états.
    ALLOWED_TRANSITIONS = {
        ApplicationStatus.RECEIVED: {
            ApplicationStatus.VIEWED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.VIEWED: {
            ApplicationStatus.INTERVIEW,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        },
        ApplicationStatus.INTERVIEW: {
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
        },
        ApplicationStatus.ACCEPTED: set(),
        ApplicationStatus.REJECTED: set(),
        ApplicationStatus.WITHDRAWN: set(),
    }

    @staticmethod
    @transaction.atomic
    def submit(
        *,
        student: StudentProfile,
        offer: InternshipOffer,
        cover_letter: str = "",
    ) -> Application:
        """Soumet une candidature."""

        if not offer.is_available:
            raise ValidationError(
                _("Cette offre n'est plus disponible.")
            )

        if Application.objects.filter(
            student=student,
            offer=offer,
        ).exists():
            raise ValidationError(
                _("Vous avez déjà candidaté à cette offre.")
            )

        return Application.objects.create(
            student=student,
            offer=offer,
            status=ApplicationStatus.RECEIVED,
            cover_letter=cover_letter,
        )

    @classmethod
    @transaction.atomic
    def change_status(
        cls,
        *,
        application: Application,
        new_status: ApplicationStatus,
    ) -> Application:
        """Change le statut d'une candidature si la transition est autorisée."""

        current_status = application.status

        allowed_statuses = cls.ALLOWED_TRANSITIONS.get(
            current_status,
            set(),
        )

        if new_status not in allowed_statuses:
            raise ValidationError(
                _(
                    "Transition impossible : %(current)s → %(new)s."
                )
                % {
                    "current": application.get_status_display(),
                    "new": new_status.label,
                }
            )

        application.status = new_status
        application.save(update_fields=["status", "updated_at"])

        return application

    @staticmethod
    @transaction.atomic
    def withdraw(application: Application) -> Application:
        """Permet à l'étudiant de retirer sa candidature."""

        if application.status in {
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        }:
            raise ValidationError(
                _("Cette candidature ne peut plus être retirée.")
            )

        application.status = ApplicationStatus.WITHDRAWN
        application.save(update_fields=["status", "updated_at"])

        return application
    