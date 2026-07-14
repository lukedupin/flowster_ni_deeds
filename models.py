from django.core.exceptions import ValidationError
from django.db import models, IntegrityError
from django.contrib import admin
import uuid


class Property(models.Model):
    id = models.AutoField(primary_key=True)

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

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
        unique_together = ('initial_address', 'deleted_on')

    def __str__(self):
        return self.initial_address

    def toJson(self):
        return {
            'uid': str(self.uid),
            'initial_address': self.initial_address,
            'found_name': self.found_name,
            'content': self.content,
            'notes': self.notes,
            'processing_log': self.processing_log,
            'deleted_on': self.deleted_on.isoformat() if self.deleted_on else None,
            'timestamp_on': self.timestamp_on.isoformat() if self.timestamp_on else None,
        }

    @staticmethod
    async def getByUid(uid):
        try:
            return await Property.objects.aget(uid=uid)
        except (Property.DoesNotExist, ValidationError):
            return None

    @staticmethod
    async def getOrCreate(initial_address):
        try:
            return await Property.objects.aget(initial_address=initial_address)
        except Property.DoesNotExist:
            pass

        try:
            return await Property.objects.acreate(initial_address=initial_address)
        except IntegrityError:
            pass

        return None

    @staticmethod
    def customAdmin():
        class Admin(admin.ModelAdmin):
            list_display = ('initial_address', 'found_name', 'deleted_on', 'timestamp_on')
            fields = ('initial_address', 'found_name', 'blob', 'content', 'notes', 'processing_log', 'deleted_on', 'timestamp_on')
            readonly_fields = ('timestamp_on',)

        return Admin
