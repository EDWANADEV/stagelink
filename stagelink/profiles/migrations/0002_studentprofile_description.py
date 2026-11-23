from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="description",
            field=models.TextField(
                blank=True,
                max_length=1000,
                verbose_name="Présentation personnelle",
            ),
        ),
    ]
