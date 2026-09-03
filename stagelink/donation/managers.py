from stagelink.core.managers import SoftDeleteManager
from stagelink.utils.enums import DonationStatus


class DonationManager(SoftDeleteManager):
    """Manager dédié aux requêtes métier des dons."""

    def pending(self):
        """Retourne les dons en attente."""
        return self.filter(status=DonationStatus.PENDING)

    def completed(self):
        """Retourne les dons effectués."""
        return self.filter(status=DonationStatus.COMPLETED)

    def failed(self):
        """Retourne les dons échoués."""
        return self.filter(status=DonationStatus.FAILED)

    def cancelled(self):
        """Retourne les dons annulés."""
        return self.filter(status=DonationStatus.CANCELLED)