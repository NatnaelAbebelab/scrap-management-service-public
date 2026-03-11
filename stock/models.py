import uuid
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import models

from stock.type_enum import StockBalanceOn

User = get_user_model()
# Create your models here.
class ScrapItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class StockBalance(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Transaction references
    transaction_type = models.CharField(
        max_length=20,
        choices=[(tag.value, tag.name) for tag in StockBalanceOn],
        default=StockBalanceOn.PURCHASE.value
    )
    grn_no = models.CharField(max_length=255, blank=True, null=True)
    record_no = models.CharField(max_length=255, blank=True, null=True)
    issue_no = models.CharField(max_length=255, blank=True, null=True)

    # Quantities
    purchased_qty = models.FloatField(default=0.0)
    issued_qty = models.FloatField(default=0.0)

    # Prices / Rates
    average_rate = models.FloatField(default=0.0)
    purchased_value = models.FloatField(default=0.0)
    issue_value = models.FloatField(default=0.0)

    # Running stock
    remaining_qty = models.FloatField(default=0.0)
    remaining_value = models.FloatField(default=0.0)

    # Date info
    weight_date = models.CharField(max_length=255, blank=True, null=True)
    record_time = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    # Audit
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_balance_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_balance_updated"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self._id)

    objects = ScrapItemManager()
    all_objects = models.Manager()

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.updated_at = datetime.today().strftime('%Y-%m-%d')
        self.save()

    def restore(self):
        self.is_deleted = False
        self.updated_at = datetime.today().strftime('%Y-%m-%d')
        self.save()

class BeginningBalance(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Quantities
    beginning_qty = models.FloatField(default=0.0)
    beginning_value = models.FloatField(default=0.0)
    current_qty = models.FloatField(default=0.0)
    current_value = models.FloatField(default=0.0)

    # Status
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    # Audit with user references
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beginning_balance_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="beginning_balance_updated"
    )
    updated_at = models.DateTimeField(auto_now=True)

    record_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self._id)

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()