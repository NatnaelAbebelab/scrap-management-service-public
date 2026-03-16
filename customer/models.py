import uuid
from datetime import datetime

from django.contrib.auth import get_user, get_user_model
from django.db import models

User = get_user_model()

class PurchaseCustomer(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(blank=True)
    last_name = models.CharField(blank=True)
    phone = models.CharField(blank=True)
    email = models.CharField(blank=True)
    TIN = models.CharField(blank=True)
    business_name = models.CharField(blank=True)
    paid_amount = models.FloatField(default=0.00)
    remaining_amount = models.FloatField(default=0.00)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_updated"
    )
    updated_at = models.DateTimeField(auto_now=True)
    record_time = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.first_name

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.updated_at = datetime.today().strftime('%Y-%m-%d')
        self.save()
