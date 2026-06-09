from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lms", "0009_storeorder_discount_ars"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollment",
            name="certificate_issued_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
