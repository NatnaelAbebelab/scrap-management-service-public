from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import datetime
import uuid
# Create your models here.
class ScrapItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("super_admin", "Super Admin"),
        ("weight_man", "Weight Man"),
        ("purchaser", "Purchaser"),
        ("inspector", "Inspector"),
        ("purchase_head", "Purchase Head"),
        ("supervisor", "Supervisor"),
        ("finance", "Finance"),
        ("manager", "General Manager"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="purchaser")
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.CharField(max_length=255, blank=True, null=True)
    record_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username
    
    objects = ScrapItemManager() # Only fetch active items
    all_objects = models.Manager() # Fetch all items

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.updated_at = datetime.today().strftime('%Y-%m-%d')
        self.save()

    def restore(self):
        self.is_deleted = False
        self.updated_at = datetime.today().strftime('%Y-%m-%d')
        self.save()