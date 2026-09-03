from stagelink.core.managers import SoftDeleteManager
from stagelink.utils.enums import PaymentStatus


class PaymentManager(SoftDeleteManager):
    """Manager dédié aux requêtes métier des paiements."""

    def pending(self):
        return self.filter(
            status=PaymentStatus.PENDING,
        )

    def successful(self):
        return self.filter(
            status=PaymentStatus.SUCCESS,
        )

    def failed(self):
        return self.filter(
            status=PaymentStatus.FAILED,
        )

    def cancelled(self):
        return self.filter(
            status=PaymentStatus.CANCELLED,
        )

    def refunded(self):
        return self.filter(
            status=PaymentStatus.REFUNDED,
        )

    def partially_refunded(self):
        return self.filter(
            status=PaymentStatus.PARTIALLY_REFUNDED,
        )