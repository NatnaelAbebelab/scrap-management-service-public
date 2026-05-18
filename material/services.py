from django.db import transaction
from django.db.models import F, Sum, DateField
from django.db.models.functions import Cast
from django.http import Http404
from django.shortcuts import get_object_or_404

from helperFunctions.validations import CastToDate
from material.enums import IssueStatus, RequisitionStatus
from material.models import MeltingPlants, MaterialRequisition, MaterialRequisitionItem, RawMaterialIssue
from stock.models import BeginningBalance
from stock.services import add_issue_balance

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
        plant_name=validated_data["plant_name"],
        created_by=user,
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

    plant.updated_by = user

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
            created_by=user
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
        requisition.unreceived_quantity = total_quantity
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

    # Cast requisition_date string to date for filtering
    requisitions = requisitions.annotate(
        requisition_date_casted=CastToDate(F("requisition_date"))
    )

    # Determine date
    if start_date:
        requisitions = requisitions.filter(
            requisition_date_casted__gte=start_date
        )

    if end_date:
        requisitions = requisitions.filter(
            requisition_date_casted__lte=end_date
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
    items_data = validated_data.get("items")

    try:
        # Fetch the requisition
        requisition = get_object_or_404(MaterialRequisition, _id=requisition_id, is_deleted=False)

        # Update main fields if provided
        assign_if_not_empty(requisition, "requisition_date", requisition_date)
        assign_if_not_empty(requisition, "requisition_no", requisition_no)

        if plant_uuid:
            melting_plant = get_object_or_404(MeltingPlants, _id=plant_uuid)
            requisition.melting_plant = melting_plant

        requisition.updated_by = user
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
        requisition.unreceived_quantity = total_quantity
        requisition.total_requisition_price = total_price
        requisition.save()

        return requisition

    except Http404:
        raise Http404("Resource not found")
    except Exception as e:
        raise Exception(f"Failed to update material requisition: {e}")

def create_raw_material_issue_service(validated_data, user):

    requisition = get_object_or_404(
        MaterialRequisition,
        _id=validated_data["material_requisition"]
    )

    issue_weight = validated_data["issue_weight"]

    # Total already issued
    total_issued = RawMaterialIssue.objects.filter(
        material_requisition=requisition,
        is_deleted=False
    ).aggregate(total=Sum("issue_weight"))["total"] or 0.0

    remaining = requisition.total_requisition_quantity - total_issued

    if total_issued >= requisition.total_requisition_quantity:
        raise ValueError("All amounts of the requisition have already been issued")

    if issue_weight > remaining:
        raise ValueError("Issue weight exceeds remaining quantity")

    issue = RawMaterialIssue.objects.create(
        material_requisition=requisition,
        issue_date=validated_data.get("issue_date"),
        issue_no=validated_data.get("issue_no"),
        issue_weight=issue_weight,
        created_by=user,
        updated_by=user
    )

    return issue

def get_raw_material_issues_service(filters):

    issues = RawMaterialIssue.objects.all()

    requisition_no = filters.get("requisition_no")
    issue_no = filters.get("issue_no")
    issue_status = filters.get("issue_status")
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")

    if requisition_no:
        issues = issues.filter(
            material_requisition__requisition_no__icontains=requisition_no
        )

    if issue_no:
        issues = issues.filter(issue_no__icontains=issue_no)

    if issue_status:
        issues = issues.filter(issue_status=issue_status)

    # Annotate the cast date for filtering (since issue_date is CharField)
    issues = issues.annotate(issue_date_casted=Cast(F("issue_date"), DateField()))

    if start_date:
        issues = issues.filter(issue_date_casted__gte=start_date)

    if end_date:
        issues = issues.filter(issue_date_casted__lte=end_date)

    return issues.order_by("-record_time")

@transaction.atomic
def edit_raw_material_issue_service(validated_data, user):
    """
    Business logic for editing a RawMaterialIssue
    """
    try:
        issue_id = validated_data["_id"]
        issue = get_object_or_404(
            RawMaterialIssue.objects.filter(
                _id=issue_id
            ).exclude(issue_status=IssueStatus.APPROVED.value)
        )

        material_requisition_id = validated_data.get("material_requisition")
        new_issue_weight = validated_data.get("issue_weight", issue.issue_weight)

        # If material_requisition is updated, fetch it and check the remaining weight
        if material_requisition_id:
            requisition = get_object_or_404(MaterialRequisition, _id=material_requisition_id)

            total_issued = RawMaterialIssue.objects.filter(
                material_requisition=requisition,
                is_deleted=False
            ).exclude(_id=issue_id).aggregate(total=Sum("issue_weight"))["total"] or 0.0

            remaining = requisition.total_requisition_quantity - total_issued

            if new_issue_weight > remaining:
                raise ValueError("Issue weight exceeds remaining quantity")

            issue.material_requisition = requisition

            # Ensure issue_date >= requisition_date if provided which is handled on the serializer

        # Update other fields if provided
        assign_if_not_empty(issue, "issue_date", validated_data.get("issue_date"))
        assign_if_not_empty(issue, "issue_no", validated_data.get("issue_no"))
        assign_if_not_empty(issue, "issue_weight", validated_data.get("issue_weight"))

        issue.updated_by = user

        issue.save()
        return issue

    except Http404:
        raise Http404("Resource not found")
    except Exception as e:
        raise Exception(f"Failed to update RawMaterialIssue: {e}")

def change_raw_material_issue_status_service(issue_id, user):
    """
    Change the status of a RawMaterialIssue:
        NEW -> ISSUED -> APPROVED
    Raises ValueError if the transition is invalid.
    Returns serialized issue and optional stock balance result.
    """
    with transaction.atomic():
        # Fetch issue excluding deleted
        issue = get_object_or_404(RawMaterialIssue, _id=issue_id, is_deleted=False)
        requisition = issue.material_requisition
        total_issued_requisition_weight = requisition.total_issued_weight

        stock_balance_result = None

        # Determine new status
        if issue.issue_status == IssueStatus.NEW.value:
            new_status = IssueStatus.ISSUED.value

        elif issue.issue_status == IssueStatus.ISSUED.value:
            if (total_issued_requisition_weight + issue.issue_weight) < requisition.total_requisition_quantity:
                new_status = IssueStatus.PARTIALLY_APPROVED.value
                new_requisition_status = RequisitionStatus.PARTIALLY_RECEIVED.value
            else:
                new_status = IssueStatus.APPROVED.value
                new_requisition_status = RequisitionStatus.RECEIVED.value

            total_issue_weight = issue.issue_weight
            unissued_weight = requisition.total_requisition_quantity - (
                        total_issued_requisition_weight + issue.issue_weight)

            # Call stock balance update logic
            stock_balance_result = add_issue_balance(
                issue_date=issue.issue_date,
                issue_no=issue.issue_no,
                issue_weight=total_issue_weight,
                melting_plant=issue.material_requisition.melting_plant,
                user=user,
            )

            # Update requisition status
            requisition.requisition_status = new_requisition_status
            requisition.unreceived_quantity = unissued_weight
            requisition.updated_by = user
            requisition.save()

        else:
            raise ValueError(f"Cannot change status from '{issue.issue_status}'")

        # Update audit and status
        issue.issue_status = new_status
        issue.updated_by = user
        issue.save()

        return issue, stock_balance_result

def filter_material_requisition_service(filters):
    queryset = (
        MaterialRequisition.objects
        .select_related("melting_plant", "created_by", "updated_by")
        .prefetch_related("items")
    )

    # Convert char date → DateField
    queryset = queryset.annotate(
        requisition_date_cast=Cast("requisition_date", DateField())
    )

    requisition_no = filters.get("requisition_no")
    start_date = filters.get("requisition_start_date")
    end_date = filters.get("requisition_end_date")
    melting_plant = filters.get("melting_plant")
    min_quantity = filters.get("min_quantity")
    max_quantity = filters.get("max_quantity")
    status = filters.get("status")

    if requisition_no:
        queryset = queryset.filter(requisition_no__icontains=requisition_no)

    if start_date:
        queryset = queryset.filter(requisition_date_cast__gte=start_date)

    if end_date:
        queryset = queryset.filter(requisition_date_cast__lte=end_date)

    if melting_plant:
        queryset = queryset.filter(melting_plant_id=melting_plant)

    if status:
        queryset = queryset.filter(requisition_status=status)

    if min_quantity:
        queryset = queryset.filter(items__quantity__gte=min_quantity)

    if max_quantity:
        queryset = queryset.filter(items__quantity__lte=max_quantity)

    return queryset.distinct()

def filter_raw_material_issue_service(filters):
    queryset = (
        RawMaterialIssue.objects
        .select_related(
            "material_requisition",
            "material_requisition__melting_plant",
            "created_by",
            "updated_by"
        )
    )

    # Cast issue_date (char → date)
    queryset = queryset.annotate(
        issue_date_cast=Cast("issue_date", DateField())
    )

    issue_no = filters.get("issue_no")
    start_date = filters.get("issue_start_date")
    end_date = filters.get("issue_end_date")
    status = filters.get("issue_status")
    melting_plant = filters.get("melting_plant")
    min_weight = filters.get("min_weight")
    max_weight = filters.get("max_weight")

    if issue_no:
        queryset = queryset.filter(issue_no__icontains=issue_no)

    if start_date:
        queryset = queryset.filter(issue_date_cast__gte=start_date)

    if end_date:
        queryset = queryset.filter(issue_date_cast__lte=end_date)

    if status:
        queryset = queryset.filter(status=status)

    # Filter by melting plant through requisition
    if melting_plant:
        queryset = queryset.filter(
            material_requisition__melting_plant_id=melting_plant
        )

    if min_weight:
        queryset = queryset.filter(issue_weight__gte=min_weight)

    if max_weight:
        queryset = queryset.filter(issue_weight__lte=max_weight)

    return queryset