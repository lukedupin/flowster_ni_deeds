from django.core.exceptions import ValidationError
from django.db import models, IntegrityError
from django.contrib import admin
import uuid


class Owner(models.Model):
    id = models.AutoField(primary_key=True)

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    initial_address = models.CharField(db_index=True, max_length=255, unique=True)
    found_name = models.CharField(unique=True, max_length=255, blank=True)

    timestamp_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'ni_deeds'

    def __str__(self):
        return self.initial_address

    def toJson(self):
        return {
            'uid': str(self.uid),
            'initial_address': self.initial_address,
            'found_name': self.found_name,
            'timestamp_on': self.timestamp_on.isoformat() if self.timestamp_on else None,
        }

    @staticmethod
    async def getByUid(uid):
        try:
            return await Owner.objects.aget(uid=uid)
        except (Owner.DoesNotExist, ValidationError):
            return None

    @staticmethod
    async def getOrCreate(initial_address):
        try:
            return await Owner.objects.aget(initial_address=initial_address)
        except Owner.DoesNotExist:
            pass

        try:
            return await Owner.objects.acreate(initial_address=initial_address)
        except IntegrityError:
            pass

        return None

    @staticmethod
    def customAdmin():
        class Admin(admin.ModelAdmin):
            list_display = ('initial_address', 'found_name', 'timestamp_on')
            fields = ('initial_address', 'found_name', 'timestamp_on')
            readonly_fields = ('timestamp_on',)

        return Admin


class Property(models.Model):
    id = models.AutoField(primary_key=True)

    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    owner = models.ForeignKey(Owner, on_delete=models.SET_NULL, null=True, blank=True, related_name='properties')

    blob = models.FileField(upload_to='ni_deeds/deeds/')
    content = models.JSONField(blank=True, default=dict)
    notes = models.TextField(blank=True, default='')
    processing_log = models.TextField(blank=True, default='')

    deleted_on = models.DateTimeField(null=True, blank=True, db_index=True)
    timestamp_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'ni_deeds'

    def __str__(self):
        return self.owner.initial_address if self.owner else str(self.uid)

    def toJson(self):
        return {
            'uid': str(self.uid),
            'initial_address': self.owner.initial_address if self.owner else None,
            'found_name': self.owner.found_name if self.owner else None,
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
        owner = await Owner.getOrCreate(initial_address)
        if owner is None:
            return None

        try:
            return await Property.objects.aget(owner=owner)
        except Property.DoesNotExist:
            pass

        try:
            return await Property.objects.acreate(owner=owner)
        except IntegrityError:
            pass

        return None

    @staticmethod
    def customAdmin():
        class Admin(admin.ModelAdmin):
            list_display = ('owner', 'deleted_on', 'timestamp_on')
            fields = ('owner', 'blob', 'content', 'notes', 'processing_log', 'deleted_on', 'timestamp_on')
            readonly_fields = ('timestamp_on',)

        return Admin
