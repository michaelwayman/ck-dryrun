from django.db import migrations

# Frozen here rather than imported, so the migration means the same thing forever.
ROLES = ["reader", "editor"]


def seed_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for name in ROLES:
        Role.objects.get_or_create(name=name)


def unseed_roles(apps, schema_editor):
    apps.get_model("accounts", "Role").objects.filter(name__in=ROLES).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [migrations.RunPython(seed_roles, unseed_roles)]
