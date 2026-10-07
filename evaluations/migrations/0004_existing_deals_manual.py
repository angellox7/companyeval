from django.db import migrations


def mark_existing_deals_manual(apps, schema_editor):
    Deal = apps.get_model("evaluations", "Deal")
    Deal.objects.all().update(evaluation_mode="manual")


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0003_ai_assessment"),
    ]

    operations = [
        migrations.RunPython(mark_existing_deals_manual, migrations.RunPython.noop),
    ]
