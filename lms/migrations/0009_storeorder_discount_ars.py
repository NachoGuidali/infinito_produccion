from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lms", "0008_fix_weight_max_digits"),
    ]

    operations = [
        migrations.AddField(
            model_name="storeorder",
            name="discount_ars",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
