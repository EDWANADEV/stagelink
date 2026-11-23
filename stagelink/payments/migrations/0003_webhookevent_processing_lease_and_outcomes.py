from django.db import migrations
from django.db import models


def initialize_processing_leases(apps, schema_editor):
    WebhookEvent = apps.get_model("payments", "WebhookEvent")
    WebhookEvent.objects.filter(
        status="processing",
        processing_started_at__isnull=True,
    ).update(processing_started_at=models.F("received_at"))


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_webhookevent_payment_idempotency_key_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="webhookevent",
            name="processing_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="last_dispatched_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(initialize_processing_leases, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="webhookevent",
            name="status",
            field=models.CharField(
                choices=[
                    ("received", "Reçu"),
                    ("processing", "En cours"),
                    ("processed", "Traité"),
                    ("ignored", "Ignoré"),
                    ("invalid", "Invalide"),
                    ("failed", "Échoué"),
                ],
                db_index=True,
                default="received",
                max_length=20,
            ),
        ),
    ]
