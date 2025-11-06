from django.db import models
from datetime import datetime
import uuid
# Create your models here.
class ScrapItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
class Rate(models.Model) :
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    heavy_rate = models.CharField(blank=True, null=True)
    medium_rate = models.CharField(blank=True, null=True)
    light_rate = models.CharField(blank=True, null=True)
    fixed_rate = models.CharField(blank=True, null=True)
    material_type = models.CharField(blank=True)
    status = models.CharField(default='expired')
    expired_date = models.CharField(blank=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.CharField(max_length=255, blank=True)
    created_at = models.CharField(max_length=255, blank=True)
    updated_by = models.CharField(max_length=255, blank=True)
    updated_at = models.CharField(max_length=255, blank=True)
    record_time = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self._id
    
    objects = ScrapItemManager()  # Only fetch active items
    all_objects = models.Manager()  # Fetch all items

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.updated_at = datetime.today().strftime('%Y-%m-%d')
        self.save()

    def restore(self):
        self.is_deleted = False
        self.updated_at = datetime.today().strftime('%Y-%m-%d')
        self.save()