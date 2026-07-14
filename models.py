from django.core.exceptions import ValidationError
from django.db import models
from django.contrib import admin
import uuid


class Property(models.Model):
    id = models.AutoField(primary_key=True)

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    initial_address = models.CharField(max_length=255)
    found_name = models.CharField(max_length=255, blank=True, null=True)

    blob = models.FileField(upload_to='ni_deeds/deeds/')
    content = models.JSONField(blank=True, default=dict)

    deleted_on = models.BooleanField(default=False)
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
            'deleted_on': self.deleted_on,
            'timestamp_on': self.timestamp_on.isoformat() if self.timestamp_on else None,
        }

    @staticmethod
    async def getByUid(uid):
        try:
            return await Property.objects.aget(uid=uid)
        except (Property.DoesNotExist, ValidationError):
            return None

    @staticmethod
    def customAdmin():
        class Admin(admin.ModelAdmin):
            list_display = ('initial_address', 'found_name', 'deleted_on', 'timestamp_on')
            fields = ('initial_address', 'found_name', 'blob', 'content', 'deleted_on', 'timestamp_on')
            readonly_fields = ('timestamp_on',)

        return Admin
