import uuid

from django.db import models


# Create your models here.
class Customer(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fname = models.CharField(blank=True)
    lname = models.CharField(blank=True)
    phone = models.CharField(blank=True)
    email = models.CharField(blank=True)
    TIN = models.CharField(blank=True)
    business_name = models.CharField(blank=True)
    paid_amount = models.FloatField(default=0.00)
    remaining_amount = models.FloatField(default=0.00)
    created_by = models.CharField(max_length=255, blank=True)
    created_at = models.CharField(max_length=255, blank=True)
    updated_by = models.CharField(max_length=255, blank=True)
    updated_at = models.CharField(max_length=255, blank=True)
    record_time = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.fname
