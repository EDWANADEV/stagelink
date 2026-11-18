from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from stagelink.core.models import BaseModel
from stagelink.offers.models import InternshipOffer
from stagelink.profiles.models import StudentProfile
from stagelink.utils.enums import ApplicationStatus


class Application(BaseModel):
    """Candidature d'un étudiant à une offre de stage."""

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name=_("Étudiant"),
    )

    offer = models.ForeignKey(
        InternshipOffer,
        on_delete=models.PROTECT,
        related_name="applications",
        verbose_name=_("Offre"),
    )

    status = models.CharField(
        _("Statut"),
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.RECEIVED,
        db_index=True,
    )

    interview_at = models.DateTimeField(
        _("Date et heure de l'entretien"),
        null=True,
        blank=True,
    )

    cover_letter = models.TextField(
        _("Lettre de motivation"),
        blank=True,
    )

    class Meta:
        verbose_name = _("Candidature")
        verbose_name_plural = _("Candidatures")
        constraints = [
            models.UniqueConstraint(
                fields=["student", "offer"],
                name="unique_student_offer_application",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student} → {self.offer}"


class ApplicationStatusHistory(models.Model):
    """Trace append-only des changements de statut d'une candidature."""

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="status_history",
        verbose_name=_("Candidature"),
    )
    previous_status = models.CharField(
        _("Ancien statut"),
        max_length=20,
        choices=ApplicationStatus.choices,
        blank=True,
    )
    new_status = models.CharField(
        _("Nouveau statut"),
        max_length=20,
        choices=ApplicationStatus.choices,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="application_status_changes",
        verbose_name=_("Auteur du changement"),
    )
    reason = models.TextField(_("Motif"), blank=True)
    created_at = models.DateTimeField(_("Date du changement"), auto_now_add=True)

    class Meta:
        verbose_name = _("Historique de candidature")
        verbose_name_plural = _("Historiques de candidature")
        ordering = ["created_at", "pk"]

    def __str__(self) -> str:
        return f"{self.application_id}: {self.previous_status} → {self.new_status}"
