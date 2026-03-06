import logging

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from grn.models import GRN
from grn.models import GRNSerialNumber
from helperFunctions.status import Status
from .workflow.transitions import get_next_status

today = timezone.now()

logger = logging.getLogger(__name__)

def is_grn_serial_number_initialized():
    try:
        return GRNSerialNumber.objects.get(status='active')
    except GRNSerialNumber.DoesNotExist:
        return None

def increment_grn_serial_number():
    try:
        active_serial_number = get_object_or_404(GRNSerialNumber.objects, status='active')
        if active_serial_number.last_used_number < active_serial_number.initial_number:
            last_used_number = active_serial_number.initial_number + 1
        else:
            last_used_number = active_serial_number.last_used_number + 1
        active_serial_number.last_used_number = last_used_number
        active_serial_number.save()
        return last_used_number
    except Http404:
        logger.error("No active GRN serial number found")
        raise Http404("No active GRN serial number found")

def filter_grn_service(role, tin=None, material_type=None, plate_no=None, start_date=None, end_date=None, status=None):
    """
    Filter GRN queryset based on optional filters and user role.
    Only apply filters if the value is not None.
    """
    grn_qs = GRN.objects.all()

    # TODO: Apply role-based filter if needed
    # grn_qs = apply_role_filter(grn_qs, role)

    if tin:
        grn_qs = grn_qs.filter(customer=tin)

    if material_type:
        grn_qs = grn_qs.filter(material_type=material_type)

    if plate_no:
        grn_qs = grn_qs.filter(plate_no__icontains=plate_no)

    if status:
        grn_qs = grn_qs.filter(status=status)

    if start_date:
        grn_qs = grn_qs.filter(first_date__gte=start_date)

    if end_date:
        grn_qs = grn_qs.filter(first_date__lte=end_date)

    return grn_qs.order_by("-record_time")

def change_grn_status_service(record_nos, role, user, data):
    """
    Unified GRN status change service.
    file_upload_service: function to handle file uploads, returns uploaded file name.
    """
    grn_no = data.get("grn_no")
    grn_img = data.get("grn_img")
    scale_img = data.get("scale_img")
    approve_img = data.get("approve_img")
    target_status = data.get("target_status")

    records = GRN.objects.filter(record_no__in=record_nos)

    skipped_records = []
    updated_records = []

    for record in records:
        next_status = get_next_status(role, record.status, target_status)
        if not next_status:
            skipped_records.append(record.record_no)
            continue

        # Role-specific updates (file names are already uploaded)
        if role == "purchaser":
            if grn_no:
                record.grn_no = grn_no
            if grn_img:
                record.grn_img = grn_img
            if scale_img:
                record.scale_img = scale_img

        elif role == "purchase_head":
            if approve_img:
                record.approve_img = approve_img

        # Update status
        record.status = next_status
        record.updated_by = user.username
        record.updated_at = today
        record.save()
        updated_records.append(record.record_no)

    return {
        "result": "success",
        "updated_records": updated_records,
        "skipped_records": skipped_records
    }

def rollback_grn_status_service(record_nos, role, user):
    """
    Roll back GRN status for the given role and record numbers.

    Rules:
    - Purchaser / Inspector / Purchase Head: rollback to previous status
    - Supervisor: handled by normal change status to 'declined'
    """
    records = GRN.objects.filter(record_no__in=record_nos)
    skipped_records = []
    rollback_records = []

    for record in records:
        current_status = record.status

        # Only rollback for allowed roles
        if role in ["purchaser", "inspector", "purchase_head"]:
            # Check if the current status belongs to the role's allowed statuses
            role_statuses = Status.get_status_by_role(role) or []
            if current_status not in role_statuses:
                skipped_records.append(record.record_no)
                continue

            # Get previous status
            previous_status = Status.get_previous_status(current_status)
            if previous_status:
                record.status = previous_status
                record.updated_by = user.username
                record.updated_at = today
                record.save()
                rollback_records.append(record.record_no)
            else:
                # No previous status to roll back to
                skipped_records.append(record.record_no)
        else:
            # Supervisor / other roles should use the normal change_status method
            skipped_records.append(record.record_no)

    return {
        "result": "success",
        "rollback_records": rollback_records,
        "skipped_records": skipped_records
    }