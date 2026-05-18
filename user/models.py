from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import BaseUserManager
from datetime import datetime
import uuid
# Create your models here.
class CustomUserManager(BaseUserManager):

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError("Username must be set")

        email = self.normalize_email(email)

        user = self.model(
            username=username,
            email=email,
            **extra_fields
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "super_admin")

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")

        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(username, email, password, **extra_fields)

class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("super_admin", "Super Admin"),
        ("weight_man", "Weight Man"),
        ("purchaser", "Purchaser"),
        ("store_keeper", "Storekeeper"),
        ("inspector", "Inspector"),
        ("purchase_head", "Purchase Head"),
        ("supervisor", "Supervisor"),
        ("finance", "Finance"),
        ("manager", "General Manager"),
        ("forman", "Forman"),
        ("department_head", "Department Head")
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="purchaser")
    phone = models.CharField(max_length=20, blank=True, null=True)
    signature = models.CharField(max_length=255, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.CharField(max_length=255, blank=True, null=True)
    record_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username
    
    objects = CustomUserManager() # Only fetch active items
    all_objects = models.Manager() # Fetch all items

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.updated_at = datetime.today().strftime('%Y-%m-%d')
        self.save()

    def restore(self):
        self.is_deleted = False
        self.updated_at = datetime.today().strftime('%Y-%m-%d')
        self.save()

    @classmethod
    def get_role_options(cls):
        """
        Returns a list of dicts for UI select:
        [{"value": "admin", "label": "Admin"}, ...]
        """
        return [{"value": value, "label": label} for value, label in cls.ROLE_CHOICES]