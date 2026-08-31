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
        default=ApplicationStatus.received,
        db_index=True,
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
