from django.db import models
from datetime import datetime
import uuid
# Create your models here.
class ScrapItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
class Agency(models.Model) :
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fname = models.CharField(blank=True, null=True)
    lname = models.CharField(blank=True, null=True)
    TIN = models.CharField(blank=True, null=False, max_length=255)
    business_name = models.CharField(blank=True, null=True)
    agreement = models.CharField(blank=True)
    remaining_amount = models.CharField(blank=True, default=0.00)
    paid_amount = models.CharField(blank=True, default=0.00)
    is_deleted = models.BooleanField(default=False)
    created_by = models.CharField(max_length=255, blank=True)
    created_at = models.CharField(max_length=255, blank=True)
    updated_by = models.CharField(max_length=255, blank=True)
    updated_at = models.CharField(max_length=255, blank=True)
    record_time = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.TIN
    
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
class Agreement(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agreement_name = models.CharField(max_length=255, blank=True)
    agency = models.CharField(max_length=255, blank=True)
    TIN = models.CharField(max_length=255, blank=True)
    material_type = models.CharField(max_length=255, blank=True, default='any')
    effective_date = models.CharField(max_length=255, blank=True)
    duration = models.CharField(max_length=255, blank=True)
    agreement_proof = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=255, blank=True, default='new')
    is_deleted = models.BooleanField(default=False)
    created_by = models.CharField(max_length=255, blank=True)
    created_at = models.CharField(max_length=255, blank=True)
    updated_by = models.CharField(max_length=255, blank=True)
    updated_at = models.CharField(max_length=255, blank=True)
    record_time = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return str(self._id)
    
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
class AgreementRange(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agreement = models.CharField(max_length=255, blank=True)
    agency = models.CharField(max_length=255, blank=True)
    min_weight = models.CharField(max_length=255, blank=True, default='1')
    max_weight = models.CharField(max_length=255, blank=True, default='1')
    rate = models.CharField(max_length=255, blank=True, default='1')
    is_deleted = models.BooleanField(default=False)
    created_by = models.CharField(max_length=255, blank=True)
    created_at = models.CharField(max_length=255, blank=True)
    updated_by = models.CharField(max_length=255, blank=True)
    updated_at = models.CharField(max_length=255, blank=True)
    record_time = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return str(self._id)
    
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
class FactoryScrapMove(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record_no = models.CharField(max_length=255, blank=True, unique=True)
    plate_no = models.CharField(max_length=255, blank=True)
    first_weight = models.CharField(max_length=255, blank=True)
    first_date = models.CharField(max_length=255, blank=True)
    first_time = models.CharField(max_length=255, blank=True)
    second_weight = models.CharField(max_length=255, blank=True)
    second_date = models.CharField(max_length=255, blank=True)
    second_time = models.CharField(max_length=255, blank=True)
    net_weight = models.CharField(max_length=255, blank=True)
    agency = models.CharField(blank=True)
    material_type = models.CharField(max_length=255, blank=True)
    type = models.CharField(max_length=255, blank=True)
    driver_name = models.CharField(max_length=255, blank=True)
    grn_no = models.CharField(blank=True, default='-')
    item_code = models.CharField(max_length=255, blank=True)
    grn_img = models.CharField(max_length=255, blank=True)
    approve_img = models.CharField(max_length=255, blank=True)
    scale_img = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=255, blank=True, default='new')
    is_deleted = models.BooleanField(default=False)
    created_by = models.CharField(max_length=255, blank=True)
    created_at = models.CharField(max_length=255, blank=True)
    updated_by = models.CharField(max_length=255, blank=True)
    updated_at = models.CharField(max_length=255, blank=True)
    record_time = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.record_no
    
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
class DailyScrapMoveAggregate(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    TIN = models.CharField(max_length=255, blank=True)
    material_type = models.CharField(max_length=255, blank=True)
    daily_net_weight = models.CharField(max_length=255, blank=True)
    rate = models.CharField(max_length=255, blank=True)
    net_price = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=255, blank=True, default='new')
    weight_date = models.CharField(max_length=255, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.CharField(max_length=255, blank=True)
    updated_at = models.CharField(max_length=255, blank=True)
    record_time = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.TIN
    
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
class ThreadTrack(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    last_weight_time = models.CharField(max_length=255, blank=True)
    record_count = models.CharField(max_length=255, blank=True)
    execution_period = models.CharField(max_length=255, blank=True)
    is_deleted = models.BooleanField(default=False)
    record_time = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.last_weight_time
    
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