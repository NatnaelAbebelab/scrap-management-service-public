from django.core.validators import MinValueValidator
from django.db import models, transaction
from datetime import datetime, timezone
import uuid
# Create your models here.
class ScrapItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    def get_active_items(self):
        return self.get_queryset().filter(status='active')
    def get_inactive_items(self):
        return self.get_queryset().filter(status='inactive')
    def get_deleted_items(self):
        return self.get_queryset().filter(status='deleted')
    def get_by_id(self, id):
        return self.get_queryset().get(id=id)

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
    serial_no = models.IntegerField(blank=True, default=0)
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

class GRNSerialNumber(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
    ]

    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    initial_number = models.IntegerField(
        validators=[MinValueValidator(10000, message="Ensure this value has at least 5 digits.")],
        help_text="Enter a 5-digit Serial code.",
        default=10000
    )

    last_used_number = models.IntegerField(
        validators=[MinValueValidator(10000, message="Ensure this value has at least 5 digits.")],
        help_text="Enter a 5-digit Serial code.",
        default=10000
    )

    status = models.CharField(max_length=255, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    is_deleted = models.BooleanField(default=False)

    created_by = models.CharField(max_length=255, blank=True)
    updated_by = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    record_time = models.DateTimeField(auto_now=True)

    objects = ScrapItemManager()
    all_objects = models.Manager()

    def __str__(self):
        return str(self._id)

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.updated_at = timezone.now()
        self.save(update_fields=["is_deleted", "updated_at"])

    def restore(self):
        self.is_deleted = False
        self.updated_at = timezone.now()
        self.save(update_fields=["is_deleted", "updated_at"])

    @transaction.atomic
    def get_next_serial(self):
        serial = GRNSerialNumber.objects.select_for_update().get(pk=self.pk)
        serial.last_used_number += 1
        serial.save(update_fields=["last_used_number"])
        return serial.last_used_number

    @classmethod
    def get_active_serial(cls):
        return cls.objects.filter(status=cls.STATUS_ACTIVE).first()