from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from stagelink.application.models import Application
from stagelink.offers.models import InternshipOffer
from stagelink.profiles.models import StudentProfile
from stagelink.utils.enums import ApplicationMode
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
        """
        Soumet une candidature à une offre.

        Une candidature ne peut être créée que si :
        - l'offre est disponible ;
        - l'offre n'est pas supprimée ;
        - l'étudiant n'a pas déjà candidaté à cette offre ;
        - la candidature est interne.
        """

        if offer.is_deleted:
            raise ValidationError(
                _("Cette offre a été supprimée.")
            )

        if not offer.is_available:
            raise ValidationError(
                _("Cette offre n'est plus disponible.")
            )

        if offer.application_mode != ApplicationMode.INTERNAL:
            raise ValidationError(
                _(
                    "Cette offre utilise une procédure de "
                    "candidature externe."
                )
            )

        if Application.objects.filter(
            student=student,
            offer=offer,
        ).exists():
            raise ValidationError(
                _("Vous avez déjà candidaté à cette offre.")
            )

        application = Application.objects.create(
            student=student,
            offer=offer,
            status=ApplicationStatus.RECEIVED,
            cover_letter=cover_letter,
            created_by=student.user,
            updated_by=student.user,
        )

        return application

    @classmethod
    @transaction.atomic
    def change_status(
        cls,
        *,
        application: Application,
        new_status: ApplicationStatus,
        updated_by=None,
    ) -> Application:
        """
        Change le statut d'une candidature si la transition
        est autorisée par le diagramme d'états.
        """

        if application.is_deleted:
            raise ValidationError(
                _("Cette candidature a été supprimée.")
            )

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

        if updated_by is not None:
            application.updated_by = updated_by

        application.save(
            update_fields=[
                "status",
                "updated_by",
                "updated_at",
            ]
        )

        return application

    @classmethod
    @transaction.atomic
    def withdraw(
        cls,
        *,
        application: Application,
        student=None,
    ) -> Application:
        """
        Permet à l'étudiant de retirer sa candidature.

        Si un StudentProfile est fourni, il doit être le propriétaire
        de la candidature.
        """

        if application.is_deleted:
            raise ValidationError(
                _("Cette candidature a été supprimée.")
            )

        if student is not None and application.student_id != student.id:
            raise ValidationError(
                _("Vous ne pouvez pas retirer cette candidature.")
            )

        if application.status in {
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        }:
            raise ValidationError(
                _("Cette candidature ne peut plus être retirée.")
            )

        application.status = ApplicationStatus.WITHDRAWN

        if student is not None:
            application.updated_by = student.user

        application.save(
            update_fields=[
                "status",
                "updated_by",
                "updated_at",
            ]
        )

        return application