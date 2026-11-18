from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from stagelink.application.models import Application
from stagelink.application.models import ApplicationStatusHistory
from stagelink.application.permissions import require_application_owner
from stagelink.application.permissions import require_offer_company
from stagelink.application.permissions import require_student
from stagelink.notifications.services import NotificationService
from stagelink.offers.models import InternshipOffer
from stagelink.utils.enums import ApplicationMode
from stagelink.utils.enums import ApplicationStatus
from stagelink.utils.enums import NotificationType

if TYPE_CHECKING:
    from stagelink.profiles.models import StudentProfile


def _validate_transition(current_status, new_status) -> None:
    if new_status == ApplicationStatus.WITHDRAWN:
        raise ValidationError(
            _("Un retrait doit être effectué par l'étudiant concerné."),
        )
    allowed_statuses = ApplicationService.ALLOWED_TRANSITIONS.get(
        current_status,
        set(),
    )
    if new_status not in allowed_statuses:
        raise ValidationError(
            _("Transition impossible : %(current)s → %(new)s.")
            % {
                "current": ApplicationStatus(current_status).label,
                "new": new_status.label,
            },
        )


def _validate_interview_schedule(new_status, interview_at) -> None:
    if new_status != ApplicationStatus.INTERVIEW:
        return
    if interview_at is None:
        raise ValidationError(
            _("Indiquez la date et l'heure prévues pour l'entretien."),
        )
    if timezone.is_naive(interview_at):
        raise ValidationError(
            _("La date de l'entretien doit inclure un fuseau horaire."),
        )


def _lock_offer_with_available_positions(application: Application):
    offer = InternshipOffer.all_objects.select_for_update().get(
        pk=application.offer_id,
    )
    accepted_count = (
        Application.all_objects.filter(
            offer=offer,
            status=ApplicationStatus.ACCEPTED,
        )
        .exclude(pk=application.pk)
        .count()
    )
    if accepted_count >= offer.available_positions:
        raise ValidationError(
            _("Toutes les places de cette offre ont déjà été attribuées."),
        )
    return offer


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
            ApplicationStatus.WITHDRAWN,
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
                _("Cette offre a été supprimée."),
            )

        if not offer.is_available:
            raise ValidationError(
                _("Cette offre n'est plus disponible."),
            )

        if offer.application_mode != ApplicationMode.INTERNAL:
            raise ValidationError(
                _(
                    "Cette offre utilise une procédure de candidature externe.",
                ),
            )

        if offer.company_id is None:
            raise ValidationError(
                _("Une offre relayée ne peut pas recevoir de candidature interne."),
            )

        require_student(student.user)
        if not student.user.email_verified:
            raise PermissionDenied

        application, created = Application.all_objects.get_or_create(
            student=student,
            offer=offer,
            defaults={
                "status": ApplicationStatus.RECEIVED,
                "cover_letter": cover_letter,
                "created_by": student.user,
                "updated_by": student.user,
            },
        )
        if not created:
            raise ValidationError(
                _("Vous avez déjà candidaté à cette offre."),
            )

        ApplicationStatusHistory.objects.create(
            application=application,
            previous_status="",
            new_status=ApplicationStatus.RECEIVED,
            changed_by=student.user,
        )
        NotificationService.create_on_commit(
            recipient_id=offer.company.user_id,
            notification_type=NotificationType.APPLICATION,
            message=_("%(student)s a candidaté à l'offre « %(offer)s ».")
            % {
                "student": student.user.name or _("Un étudiant"),
                "offer": offer.title,
            },
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
        interview_at=None,
    ) -> Application:
        """
        Change le statut d'une candidature si la transition
        est autorisée par le diagramme d'états.
        """

        try:
            new_status = ApplicationStatus(new_status)
        except ValueError as exc:
            raise ValidationError(_("Statut de candidature inconnu.")) from exc

        application = (
            Application.all_objects.select_for_update()
            .select_related("student__user", "offer__company")
            .get(pk=application.pk)
        )
        if application.is_deleted:
            raise ValidationError(
                _("Cette candidature a été supprimée."),
            )

        if updated_by is None:
            raise PermissionDenied
        require_offer_company(updated_by, application)
        current_status = application.status
        _validate_transition(current_status, new_status)
        _validate_interview_schedule(new_status, interview_at)

        if new_status == ApplicationStatus.ACCEPTED:
            application.offer = _lock_offer_with_available_positions(application)

        previous_status = application.status
        application.status = new_status
        update_fields = ["status", "updated_by", "updated_at"]
        if new_status == ApplicationStatus.INTERVIEW:
            application.interview_at = interview_at
            update_fields.append("interview_at")

        if updated_by is not None:
            application.updated_by = updated_by

        application.save(update_fields=update_fields)
        ApplicationStatusHistory.objects.create(
            application=application,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=updated_by,
        )
        NotificationService.create_on_commit(
            recipient_id=application.student.user_id,
            notification_type=NotificationType.APPLICATION,
            message=(
                _(
                    "Le statut de votre candidature à « %(offer)s » "
                    "est maintenant « %(status)s ».",
                )
                % {
                    "offer": application.offer.title,
                    "status": application.get_status_display(),
                }
            ),
        )

        return application

    @classmethod
    @transaction.atomic
    def withdraw(
        cls,
        *,
        application: Application,
        student=None,
        reason: str = "",
    ) -> Application:
        """
        Permet à l'étudiant de retirer sa candidature.

        Si un StudentProfile est fourni, il doit être le propriétaire
        de la candidature.
        """

        application = (
            Application.all_objects.select_for_update()
            .select_related("student__user", "offer__company")
            .get(pk=application.pk)
        )
        reason = (reason or "").strip()
        if application.is_deleted:
            raise ValidationError(
                _("Cette candidature a été supprimée."),
            )

        if student is None:
            raise PermissionDenied
        require_application_owner(student.user, application)

        if application.status in {
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        }:
            raise ValidationError(
                _("Cette candidature ne peut plus être retirée."),
            )

        if application.status == ApplicationStatus.INTERVIEW:
            if not reason:
                raise ValidationError(
                    _(
                        "Un motif est obligatoire pour retirer une candidature "
                        "à l'entretien.",
                    ),
                )
            if application.interview_at is None:
                raise ValidationError(
                    _(
                        "Le retrait est impossible car l'entretien n'a pas "
                        "de date prévue.",
                    ),
                )
            if timezone.now() > application.interview_at - timedelta(hours=24):
                raise ValidationError(
                    _(
                        "Le retrait doit être effectué au moins 24 heures "
                        "avant l'entretien.",
                    ),
                )

        previous_status = application.status
        application.status = ApplicationStatus.WITHDRAWN

        application.updated_by = student.user

        application.save(
            update_fields=[
                "status",
                "updated_by",
                "updated_at",
            ],
        )
        ApplicationStatusHistory.objects.create(
            application=application,
            previous_status=previous_status,
            new_status=ApplicationStatus.WITHDRAWN,
            changed_by=student.user,
            reason=reason,
        )
        NotificationService.create_on_commit(
            recipient_id=application.offer.company.user_id,
            notification_type=NotificationType.APPLICATION,
            message=_("%(student)s a retiré sa candidature à l'offre « %(offer)s ».")
            % {
                "student": student.user.name or _("Un étudiant"),
                "offer": application.offer.title,
            },
        )

        return application
