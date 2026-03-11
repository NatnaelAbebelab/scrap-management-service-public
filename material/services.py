from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from helperFunctions.validations import CastToDate
from material.models import MeltingPlants, MaterialRequisition, MaterialRequisitionItem
from stock.models import BeginningBalance

def assign_if_not_empty(obj, field_name, value):
    """
    Helper to update a field only if the value is not None or blank.
    """
    if value is not None and value != "":
        setattr(obj, field_name, value)

def create_melting_plant(validated_data, user):
    """
    Business logic for creating a melting plant
    """

    plant = MeltingPlants.objects.create(
        plant_name=validated_data["plant"],
        created_by=user.username,
        created_by_id=user,
    )

    return plant

def update_melting_plant(melting_plant_id, validated_data, user):
    """
    Update an existing melting plant
    """

    # Fetch existing plant
    try:
        plant = MeltingPlants.objects.get(_id=melting_plant_id)
    except MeltingPlants.DoesNotExist:
        return None

    # Update fields
    if "plant_name" in validated_data:
        plant.plant_name = validated_data["plant_name"]

    plant.updated_by = user.username
    plant.updated_by_id = user

    plant.save()
    return plant

@transaction.atomic
def create_material_requisition(validated_data, user):
    """
    Creates a material requisition and associated items
    while checking the current balance.
    """
    try:
        # Fetch melting plant
        melting_plant = get_object_or_404(MeltingPlants, _id=validated_data["plant"])

        # Check the current balance
        active_balance = BeginningBalance.objects.filter(is_active=True, is_deleted=False).first()
        current_qty = float(active_balance.current_qty) if active_balance and active_balance.current_qty else 0.0

        # Create requisition
        requisition = MaterialRequisition.objects.create(
            melting_plant=melting_plant,
            requisition_date=validated_data["requisition_date"],
            requisition_no=validated_data["requisition_no"],
            created_by=user.username,
            created_by_id=user
        )

        total_quantity = 0
        total_price = 0

        for item_data in validated_data["items"]:
            quantity = item_data["quantity"]
            unit_price = item_data["unit_price"]
            total_item_price = quantity * unit_price

            total_quantity += quantity
            total_price += total_item_price

            if total_quantity > current_qty:
                # Rollback created requisition
                requisition.delete()
                raise ValueError("Total requisition quantity exceeds the current balance")

            MaterialRequisitionItem.objects.create(
                material_requisition=requisition,
                item_code=item_data["item_code"],
                item_name=item_data["item_name"],
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_item_price
            )

        # Update totals
        requisition.total_requisition_quantity = total_quantity
        requisition.total_requisition_price = total_price
        requisition.save()

        return requisition

    except Http404:
        raise Http404("Melting plant not found")
    except Exception as e:
        raise Exception(f"Failed to create material requisition: {e}")

def get_filtered_material_requisitions(filters):
    """
    Returns a queryset of material requisitions with filters:
    - plant: UUID of MeltingPlants (foreign key)
    - start_date / end_date: date range
    - requisition_no
    - status
    """
    requisitions = MaterialRequisition.objects.order_by("-record_time")

    plant = filters.get("plant")
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    requisition_no = filters.get("requisition_no")
    status = filters.get("status")

    today = timezone.now().date()

    # Determine end_date
    if not end_date:
        end_date = today

    # Determine start_date
    if not start_date:
        start_date = end_date - timedelta(days=60)

    # Cast requisition_date string to date for filtering
    requisitions = requisitions.annotate(
        requisition_date_casted=CastToDate(F("requisition_date"))
    ).filter(
        requisition_date_casted__range=[start_date, end_date]
    )

    # Plant filter (UUID -> FK)
    if plant:
        requisitions = requisitions.filter(melting_plant_id=plant)

    # Other filters
    if requisition_no:
        requisitions = requisitions.filter(requisition_no__icontains=requisition_no)
    if status:
        requisitions = requisitions.filter(requisition_status=status)

    return requisitions

@transaction.atomic
def update_material_requisition(user, validated_data):
    """
    Updates a material requisition and its items.

    Only updates fields/items that are provided (not None or blank).
    """
    requisition_id = validated_data["_id"]
    plant_uuid = validated_data.get("plant")
    requisition_date = validated_data.get("requisition_date")
    requisition_no = validated_data.get("requisition_no")
    items_data = validated_data.get("items", [])

    try:
        # Fetch the requisition
        requisition = get_object_or_404(MaterialRequisition, _id=requisition_id, is_deleted=False)

        # Update main fields if provided
        assign_if_not_empty(requisition, "requisition_date", requisition_date)
        assign_if_not_empty(requisition, "requisition_no", requisition_no)

        if plant_uuid:
            melting_plant = get_object_or_404(MeltingPlants, _id=plant_uuid)
            requisition.melting_plant = melting_plant

        requisition.updated_by = user.username
        requisition.updated_by_id = user
        requisition.save()

        # --- Handle items ---
        existing_items = {str(i._id): i for i in requisition.items.all()}
        received_ids = set()
        total_quantity = 0
        total_price = 0

        for item_data in items_data:
            item_id = str(item_data.get("_id")) if item_data.get("_id") else None
            quantity = float(item_data.get("quantity", 0))
            unit_price = float(item_data.get("unit_price", 0))
            total_item_price = quantity * unit_price

            # Update existing item
            if item_id and item_id in existing_items:
                item = existing_items[item_id]
                assign_if_not_empty(item, "item_code", item_data.get("item_code"))
                assign_if_not_empty(item, "item_name", item_data.get("item_name"))
                assign_if_not_empty(item, "quantity", quantity)
                assign_if_not_empty(item, "unit_price", unit_price)
                assign_if_not_empty(item, "total_price", total_item_price)
                item.save()
                received_ids.add(item_id)
            else:
                # Create a new item
                MaterialRequisitionItem.objects.create(
                    material_requisition=requisition,
                    item_code=item_data.get("item_code", ""),
                    item_name=item_data.get("item_name", ""),
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_item_price
                )

            total_quantity += quantity
            total_price += total_item_price

        # Delete removed items
        for item_id, item in existing_items.items():
            if item_id not in received_ids:
                item.delete()

        # Update totals
        requisition.total_requisition_quantity = total_quantity
        requisition.total_requisition_price = total_price
        requisition.save()

        return requisition

    except Http404:
        raise Http404("Resource not found")
    except Exception as e:
        raise Exception(f"Failed to update material requisition: {e}")