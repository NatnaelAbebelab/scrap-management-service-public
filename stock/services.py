from django.db import transaction

from stock.models import BeginningBalance


def create_beginning_balance(beginning_qty, beginning_value, user):
    """
    Creates a new beginning balance and deactivates the previous active one.
    """
    with transaction.atomic():
        active_balance = BeginningBalance.objects.filter(is_active=True).first()
        if active_balance:
            active_balance.is_active = False
            active_balance.updated_by = user
            active_balance.save()

        new_balance = BeginningBalance.objects.create(
            beginning_qty=beginning_qty,
            beginning_value=beginning_value,
            current_qty=beginning_qty,
            current_value=beginning_value,
            is_active=True,
            created_by=user,
            updated_by=user,
        )

    return new_balance