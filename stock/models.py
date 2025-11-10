import uuid
from datetime import datetime
from django.db import models

# Create your models here.
class ScrapItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class StockBalance(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_weight = models.FloatField(max_length=255, default=0.0)
    transport_weight = models.FloatField(max_length=255, default=0.0)
    net_weight = models.FloatField(max_length=255, default=0.0)
    weight_date = models.CharField(max_length=255, blank=True)
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


class BalanceHistory(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record_no = models.CharField(max_length=255, blank=False)
    type = models.CharField(max_length=255, blank=False)
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

class CumulativeBalance(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    beginning_balance = models.FloatField(max_length=255, default=0.0)
    current_balance = models.FloatField(max_length=255, default=0.0)
    is_active = models.BooleanField(default=True) # False when a new beginning record is created
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