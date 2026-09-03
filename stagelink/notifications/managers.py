from stagelink.core.managers import SoftDeleteManager


class NotificationManager(SoftDeleteManager):
    """Manager dédié aux requêtes métier des notifications."""

    def unread(self):
        """Retourne les notifications non lues."""
        return self.filter(is_read=False)

    def read(self):
        """Retourne les notifications déjà lues."""
        return self.filter(is_read=True)