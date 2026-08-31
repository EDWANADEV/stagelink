from django.utils import timezone

from stagelink.core.managers import SoftDeleteManager
from stagelink.utils.enums import OfferStatus


class InternshipOfferManager(SoftDeleteManager):
    """Manager dédié aux requêtes métier des offres."""

    def available(self):
        """Retourne les offres actuellement disponibles."""

        return self.filter(
            status=OfferStatus.PUBLISHED,
            application_deadline__gte=timezone.now(),
        )
