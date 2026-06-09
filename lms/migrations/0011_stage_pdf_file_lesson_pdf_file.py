from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lms", "0010_enrollment_certificate_issued_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="stage",
            name="pdf_file",
            field=models.FileField(blank=True, null=True, upload_to="stage_pdfs/"),
        ),
        migrations.AddField(
            model_name="lesson",
            name="pdf_file",
            field=models.FileField(blank=True, null=True, upload_to="lesson_pdfs/"),
        ),
    ]
