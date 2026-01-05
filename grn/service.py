from django.shortcuts import get_object_or_404
from grn.models import GRNSerialNumber

def increment_grn_serial_number():
    active_serial_number = get_object_or_404(GRNSerialNumber.objects, status='active')
    if active_serial_number.last_used_number < active_serial_number.initial_number:
        last_used_number = active_serial_number.initial_number + 1
    else:
        last_used_number = active_serial_number.last_used_number + 1
    active_serial_number.last_used_number = last_used_number
    active_serial_number.save()
    return last_used_number
