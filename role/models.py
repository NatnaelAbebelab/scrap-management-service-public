from django.db import models
import uuid
# Create your models here.
class Role(models.Model) :
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(blank=True)
    assigned_users = models.IntegerField(default=0)
    created_by = models.CharField(max_length=255, blank=True)
    created_at = models.CharField(max_length=255, blank=True)
    updated_by = models.CharField(max_length=255, blank=True)
    updated_at = models.CharField(max_length=255, blank=True)
    def __str__(self):
        return self.name