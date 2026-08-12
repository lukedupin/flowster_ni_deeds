from django.db import migrations
from django.db import models, IntegrityError
import uuid


def populate_owners(apps, schema_editor):
    class Owner0007(models.Model):
        id = models.AutoField(primary_key=True)

        uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

        initial_address = models.CharField(max_length=255, unique=True)
        found_name = models.CharField(max_length=255, blank=True, null=True)

        timestamp_on = models.DateTimeField(auto_now_add=True)

        class Meta:
            app_label = 'ni_deeds'
            db_table = 'ni_deeds_owner'

    class Property0007(models.Model):
        id = models.AutoField(primary_key=True)

        uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

        owner = models.ForeignKey(Owner0007, on_delete=models.SET_NULL, null=True, blank=True, related_name='properties')

        initial_address = models.CharField(max_length=255)
        found_name = models.CharField(max_length=255, blank=True, null=True)

        blob = models.FileField(upload_to='ni_deeds/deeds/')
        content = models.JSONField(blank=True, default=dict)
        notes = models.TextField(blank=True, default='')
        processing_log = models.TextField(blank=True, default='')

        deleted_on = models.DateTimeField(null=True, blank=True, db_index=True)
        timestamp_on = models.DateTimeField(auto_now_add=True)

        class Meta:
            app_label = 'ni_deeds'
            db_table = 'ni_deeds_property'

    for prop in Property0007.objects.all():
        owner, _ = Owner0007.objects.get_or_create(
            initial_address=prop.initial_address,
            defaults={'found_name': prop.found_name},
        )
        prop.owner = owner
        prop.save()


class Migration(migrations.Migration):

    dependencies = [
        ('ni_deeds', '0006_owner_alter_property_unique_together_property_owner_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_owners, migrations.RunPython.noop),
    ]
