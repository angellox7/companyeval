from django.db import migrations


def seed_benchmarks(apps, schema_editor):
    SectorBenchmark = apps.get_model("evaluations", "SectorBenchmark")
    from evaluations.constants import DEFAULT_BENCHMARKS

    SectorBenchmark.objects.bulk_create(
        [SectorBenchmark(**row) for row in DEFAULT_BENCHMARKS]
    )


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_benchmarks, migrations.RunPython.noop),
    ]
