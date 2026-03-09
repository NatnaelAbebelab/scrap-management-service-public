from django.db import transaction

from stock.models import BeginningBalance, StockBalance


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

def add_purchase_stock_record(date_str, purchase_qty, purchase_value, grn_no, record_no,
                              heavy_rate=0, medium_rate=0, light_rate=0, user=None):
    """
    Create a StockBalance record for a single GRN.
    Each GRN is treated individually.
    - Calculates cumulative remaining_qty / remaining_value
    - Calculates average_rate from heavy, medium, light rates
    """
    with transaction.atomic():
        # Get the last stock record to calculate cumulative remaining_qty/value
        last_stock = StockBalance.objects.filter(is_deleted=False).order_by("-record_time").first()

        if last_stock:
            prev_remaining_qty = last_stock.remaining_qty
            prev_remaining_value = last_stock.remaining_value
        else:
            # Use beginning balance if no stock exists
            beginning_balance = BeginningBalance.objects.filter(is_active=True).first()
            prev_remaining_qty = beginning_balance.current_qty if beginning_balance else 0
            prev_remaining_value = beginning_balance.current_value if beginning_balance else 0

        # New cumulative remaining
        new_remaining_qty = prev_remaining_qty + purchase_qty
        new_remaining_value = prev_remaining_value + purchase_value

        # Average rate calculation
        rates = [r for r in [heavy_rate, medium_rate, light_rate] if r > 0]
        average_rate = sum(rates) / len(rates) if rates else 0

        # Create a new stock record
        stock = StockBalance(
            weight_date=date_str,
            grn_no=grn_no,
            record_no=record_no,
            purchased_qty=purchase_qty,
            purchased_value=purchase_value,
            remaining_qty=new_remaining_qty,
            remaining_value=new_remaining_value,
            average_rate=average_rate,
            created_by=user,
            updated_by=user
        )

        return stock