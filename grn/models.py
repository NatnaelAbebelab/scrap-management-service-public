from django.db import models
from datetime import datetime
import uuid
# Create your models here.
class ScrapItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
class GRN(models.Model) :
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
    customer = models.CharField(blank=True)
    type = models.CharField(max_length=255, blank=True)
    material_type = models.CharField(max_length=255, blank=True)
    heavy_grade = models.CharField(max_length=255, blank=True)
    medium_grade = models.CharField(max_length=255, blank=True)
    light_grade = models.CharField(max_length=255, blank=True)
    heavy_rate = models.CharField(max_length=255, blank=True, default="0")
    medium_rate = models.CharField(max_length=255, blank=True, default="0")
    light_rate = models.CharField(max_length=255, blank=True, default="0")
    fixed_rate = models.CharField(max_length=255, blank=True, default="0")
    driver_name = models.CharField(max_length=255, blank=True)
    grn_no = models.CharField(blank=True, default='-')
    net_price = models.CharField(max_length=255, blank=True, default='0.0')
    waste_deduction = models.CharField(max_length=255, blank=True, default='0.0') 
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