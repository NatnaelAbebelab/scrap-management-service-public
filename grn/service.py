import logging

from django.http import Http404
from django.shortcuts import get_object_or_404

from grn.models import GRN
from grn.models import GRNSerialNumber

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
