import uuid

from django.db import models

from material.enums import RequisitionStatus, IssueStatus
from user.models import CustomUser


# Create your models here.
class ScrapItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class MeltingPlants(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plant_name = models.CharField(max_length=255, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="plant_created_by")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="plant_updated_by")
    updated_at = models.DateTimeField(auto_now=True)
    record_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self._id)

    objects = ScrapItemManager()
    all_objects = models.Manager()

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()

class MaterialRequisition(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    melting_plant = models.ForeignKey(MeltingPlants, on_delete=models.SET_NULL, null=True, blank=True)
    requisition_date = models.CharField(max_length=255, blank=True)
    requisition_no = models.CharField(max_length=255, blank=True)
    total_requisition_quantity = models.FloatField(max_length=255, default=0.0)
    total_requisition_price = models.FloatField(max_length=255, default=0.0)
    requisition_status = models.CharField(
        max_length=50,
        choices=[(s.value, s.name.title()) for s in RequisitionStatus],
        default=RequisitionStatus.REQUESTED.value
    )
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="requisition_created_by")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="requisition_updated_by")
    updated_at = models.DateTimeField(auto_now=True)
    record_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self._id

    objects = ScrapItemManager()
    all_objects = models.Manager()

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()

class MaterialRequisitionItem(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material_requisition = models.ForeignKey(MaterialRequisition, on_delete=models.CASCADE, related_name="items")
    item_code = models.CharField(max_length=255, blank=True)
    item_name = models.CharField(max_length=255, blank=True)
    quantity = models.FloatField(default=0.0)
    unit_price = models.FloatField()
    total_price = models.FloatField()

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_code} - {self.item_name}"

class RawMaterialIssue(models.Model):
    _id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    material_requisition = models.ForeignKey(MaterialRequisition, on_delete=models.CASCADE)
    issue_date = models.CharField(max_length=255, blank=True)
    issue_no = models.CharField(max_length=255, blank=True)
    issue_status = models.CharField(
        max_length=50,
        choices=[(s.value, s.name.title()) for s in IssueStatus],
        default=IssueStatus.NEW.value
    )
    issue_weight = models.FloatField(default=0.0)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="issue_created_by")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="issue_updated_by")
    updated_at = models.DateTimeField(auto_now=True)
    record_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self._id)

    objects = ScrapItemManager()
    all_objects = models.Manager()

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()

    def restore(self):
        self.is_deleted = False
        self.save()