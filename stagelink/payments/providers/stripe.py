import stripe
from django.conf import settings


class StripeService:
    @staticmethod
    def _configure():
        stripe.api_key = settings.STRIPE_SECRET_KEY

    @classmethod
    def create_payment_intent(cls, *, payment):
        cls._configure()

        intent = stripe.PaymentIntent.create(
            amount=int(payment.amount.amount),
            currency=payment.amount.currency.code.lower(),
            payment_method_types=["card"],
            metadata={
                "stagelink_payment_id": str(payment.id),
                "donation_id": str(payment.donation_id),
            },
            idempotency_key=f"payment:{payment.id}",
        )

        response = intent.to_dict_recursive()

        # Ne jamais conserver le client_secret dans notre base.
        response.pop("client_secret", None)

        return {
            "id": intent.id,
            "client_secret": intent.client_secret,
            "response": response,
        }