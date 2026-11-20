import stripe
from django.conf import settings


class StripeService:
    @staticmethod
    def _configure():
        if (
            not settings.STRIPE_PUBLISHABLE_KEY.startswith(("pk_test_", "pk_live_"))
            or not settings.STRIPE_SECRET_KEY.startswith(("sk_test_", "sk_live_"))
            or not settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_")
            or any(
                marker in value.lower()
                for value in (
                    settings.STRIPE_PUBLISHABLE_KEY,
                    settings.STRIPE_SECRET_KEY,
                    settings.STRIPE_WEBHOOK_SECRET,
                )
                for marker in ("replace", "xxxxx", "placeholder")
            )
        ):
            raise ValueError("Stripe n'est pas configuré.")
        stripe.api_key = settings.STRIPE_SECRET_KEY

    @classmethod
    def create_payment_intent(cls, *, payment):
        if not settings.STRIPE_ENABLED:
            raise ValueError("Stripe est désactivé.")
        cls._configure()

        currency = payment.amount.currency.code.lower()
        zero_decimal_currencies = {
            "bif",
            "clp",
            "djf",
            "gnf",
            "jpy",
            "kmf",
            "krw",
            "mga",
            "pyg",
            "rwf",
            "ugx",
            "vnd",
            "vuv",
            "xaf",
            "xof",
            "xpf",
        }
        amount = (
            int(payment.amount.amount)
            if currency in zero_decimal_currencies
            else int(payment.amount.amount * 100)
        )

        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
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

    @classmethod
    def retrieve_payment_intent(cls, payment_intent_id):
        cls._configure()
        return stripe.PaymentIntent.retrieve(payment_intent_id)
