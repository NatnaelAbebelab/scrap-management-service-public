import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import DateField, Count, Sum, Func, F, FloatField
from django.db.models.functions import Cast, TruncDay, TruncWeek, TruncMonth, TruncQuarter, TruncYear
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from customer.models import PurchaseCustomer
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

    allowed_statuses = Status.get_status_by_role(role)

    if allowed_statuses:
        grn_qs = grn_qs.filter(status__in=allowed_statuses)

    if tin:
        grn_qs = grn_qs.filter(customer=tin)

    if material_type:
        grn_qs = grn_qs.filter(material_type=material_type)

    if plate_no:
        grn_qs = grn_qs.filter(plate_no__icontains=plate_no)

    if status and status in allowed_statuses:
        grn_qs = grn_qs.filter(status__in=status)

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

def pay_customer_service(record_numbers, user):

    with transaction.atomic():

        grns = GRN.objects.select_for_update().filter(
            record_no__in=record_numbers,
            status__in=[
                Status.APPROVED.status_value,
                Status.APPROVED_MANAGER.status_value
            ]
        )

        if not grns.exists():
            raise ValueError("No valid GRN records found")

        # ensure all GRNs belong to the same customer
        tins = list(GRN.objects.filter(record_no__in=record_numbers).values_list("customer", flat=True).distinct())

        if len(tins) != 1:
            raise ValueError("All GRNs must belong to the same customer")

        tin = tins[0]

        customer = get_object_or_404(
            PurchaseCustomer.objects.select_for_update(),
            TIN=tin
        )

        total_amount = sum(
            Decimal(g.net_price) for g in grns
        )

        if total_amount > Decimal(customer.remaining_amount):
            raise ValueError("Paid amount exceeds available balance")

        # update customer
        customer.paid_amount = Decimal(customer.paid_amount) + total_amount
        customer.remaining_amount = Decimal(customer.remaining_amount) - total_amount
        customer.updated_by = user.username
        customer.updated_at = today
        customer.save()

        # update GRN status
        grns.update(
            status=Status.PAID.status_value,
            updated_by=user.username,
            updated_at=today
        )

        return {
            "customer_tin": tin,
            "paid_records": grns.count(),
            "total_paid": total_amount
        }

def filter_grn_report_service(filters):

    tin = filters.get("tin")
    material_type = filters.get("material_type")
    plate_no = filters.get("plate_no")
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    status = filters.get("status")

    # allowed_status = Status.get_status_by_role(role)
    #
    # if status and status not in allowed_status:
    #     raise StatusException(f"{status} is not allowed for role {role}")

    queryset = GRN.objects.all()

    # TIN filter
    if tin:
        if PurchaseCustomer.objects.filter(TIN=tin).exists():
            queryset = queryset.filter(customer=tin)

    # Material type
    if material_type:
        queryset = queryset.filter(material_type__iexact=material_type)

    # Plate number
    if plate_no:
        queryset = queryset.filter(plate_no__iexact=plate_no)

    # Convert string date to date
    queryset = queryset.annotate(
        first_date_casted=Func(
            F("first_date"),
            function="TO_DATE",
            template="TO_DATE(%(expressions)s, 'DD.MM.YYYY')",
            output_field=DateField()
        )
    )

    if start_date:
        queryset = queryset.filter(first_date_casted__gte=start_date)

    if end_date:
        queryset = queryset.filter(first_date_casted__lte=end_date)

    # Status filtering
    if status:
        queryset = queryset.filter(status=status)

    return queryset.order_by("-record_time")

def generate_grn_periodic_report(filters):
    """
    Generate a GRN periodic report based on filters.
    """
    tin = filters.get("tin")
    material_type = filters.get("material_type")
    plate_no = filters.get("plate_no")
    status = filters.get("status")
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    period = filters.get("period") or "daily"

    # -------- Date Defaults --------

    if not end_date:
        end_date = today

    if not start_date:
        start_date = end_date - timedelta(days=60)

    # -------- Base Query --------

    qs = GRN.objects.all().annotate(
        first_date_casted=Func(
            F("first_date"),
            function="TO_DATE",
            template="TO_DATE(%(expressions)s, 'DD.MM.YYYY')",
            output_field=DateField()
        )
    )

    qs = qs.filter(
        first_date_casted__gte=start_date,
        first_date_casted__lte=end_date
    )

    # -------- Optional Filters --------

    if tin:
        qs = qs.filter(customer=tin)

    if material_type:
        qs = qs.filter(material_type__iexact=material_type)

    if plate_no:
        qs = qs.filter(plate_no__icontains=plate_no)

    if status:
        qs = qs.filter(status=status)

    # -------- Period Grouping --------

    trunc_map = {
        "daily": TruncDay,
        "weekly": TruncWeek,
        "monthly": TruncMonth,
        "quarterly": TruncQuarter,
        "yearly": TruncYear,
    }

    trunc_function = trunc_map.get(period, TruncDay)

    report = (
        qs.annotate(period_group=trunc_function("first_date_casted"))
        .annotate(
            net_weight_float=Cast("net_weight", FloatField()),
            net_price_float=Cast("net_price", FloatField()),
        )
        .values("period_group")
        .annotate(
            total_records=Count("record_no"),
            total_weight=Sum("net_weight_float"),
            total_price=Sum("net_price_float"),
        )
        .order_by("period_group")
    )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "period": period,
        "data": list(report),
    }