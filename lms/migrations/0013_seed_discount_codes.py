from django.db import migrations


def crear_codigos_iniciales(apps, schema_editor):
    """
    Los códigos vivían hardcodeados en views_store.py. Se migra únicamente
    el vigente, ya renombrado a "infi20"; "agosto30" se descarta.
    """
    DiscountCode = apps.get_model("lms", "DiscountCode")
    DiscountCode.objects.get_or_create(
        code="infi20",
        defaults={"percent": 20, "is_active": True},
    )


def borrar_codigos_iniciales(apps, schema_editor):
    DiscountCode = apps.get_model("lms", "DiscountCode")
    DiscountCode.objects.filter(code="infi20").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("lms", "0012_discountcode"),
    ]

    operations = [
        migrations.RunPython(crear_codigos_iniciales, borrar_codigos_iniciales),
    ]
