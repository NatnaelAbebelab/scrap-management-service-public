import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Sum
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncQuarter, TruncYear
from django.utils import timezone

from helperFunctions.date_manipulation import normalize_date_string
from helperFunctions.validations import ToFormalDate
from stock.models import BeginningBalance, StockBalance
from stock.serializers import StockBalanceSerializer
from stock.type_enum import StockBalanceOn

logger = logging.getLogger(__name__)

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

        # Update the current active beginning balance
        active_balance = BeginningBalance.objects.filter(
            is_active=True
        ).first()
        active_balance.current_qty += purchase_qty
        active_balance.current_value += purchase_value
        active_balance.save()

        # change weight date string format
        weight_date_str = normalize_date_string(date_str)

        # Create a new stock record
        stock = StockBalance(
            weight_date=weight_date_str,
            transaction_type=StockBalanceOn.PURCHASE.value,
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

def get_stock_balance_service(filters: dict):
    """
    Fetch stock balance records based on type and date range.

    Rules:
    - If end_date is null → use today
    - If start_date is null → 60 days before end_date
    - Type can be purchased, issue, or None (both)
    """

    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    balance_type = filters.get("type")

    today = timezone.now().date()

    # Default end date
    if not end_date:
        end_date = today

    # Default start date
    if not start_date:
        start_date = end_date - timedelta(days=60)

    queryset = (
        StockBalance.objects
        .annotate(weight_date_dt=ToFormalDate(F("weight_date")))
        .filter(weight_date_dt__range=(start_date, end_date))
        .order_by("weight_date_dt") # ascending = oldest first
    )

    # Apply type filter
    if balance_type == StockBalanceOn.PURCHASE.value:
        queryset = queryset.filter(transaction_type=StockBalanceOn.PURCHASE.value)

    elif balance_type == StockBalanceOn.ISSUE.value:
        queryset = queryset.filter(transaction_type=StockBalanceOn.ISSUE.value)

    return queryset

def get_stock_balance_aggregated_service(filters: dict):
    """
    Fetch aggregated stock balance report by period.
    Periods: daily (default), weekly, monthly, quarterly, yearly
    Aggregates: purchased_qty, purchased_value, issued_qty, issued_value
    """
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    balance_type = filters.get("type")
    period = filters.get("period", "daily")

    today = timezone.now().date()
    if not end_date:
        end_date = today
    if not start_date:
        start_date = end_date - timedelta(days=60)

    # Base queryset
    queryset = StockBalance.objects.annotate(
        weight_date_dt=ToFormalDate(F("weight_date"))
    ).filter(
        weight_date_dt__range=(start_date, end_date)
    )

    # Apply type filter
    if balance_type == StockBalanceOn.PURCHASE.value:
        queryset = queryset.filter(transaction_type=StockBalanceOn.PURCHASE.value)
    elif balance_type == StockBalanceOn.ISSUE.value:
        queryset = queryset.filter(transaction_type=StockBalanceOn.ISSUE.value)

    # Truncate by period
    if period == "daily":
        trunc_func = TruncDay("weight_date_dt")
    elif period == "weekly":
        trunc_func = TruncWeek("weight_date_dt")
    elif period == "monthly":
        trunc_func = TruncMonth("weight_date_dt")
    elif period == "quarterly":
        trunc_func = TruncQuarter("weight_date_dt")
    elif period == "yearly":
        trunc_func = TruncYear("weight_date_dt")
    else:
        trunc_func = TruncDay("weight_date_dt")  # default daily

    queryset = queryset.annotate(period_group=trunc_func).values("period_group").annotate(
        total_purchase=Sum("purchased_qty"),
        total_purchase_value=Sum("purchased_value"),
        total_issue=Sum("issued_qty"),
        total_issue_value=Sum("issue_value"),
    ).order_by("period_group")

    return queryset

def generate_stock_card_service(filters: dict):
    """
    Generate stock card totals by summing purchase and issue quantities and values
    between start_date and end_date.
    Converts weight_date from string to date before filtering using ToDate.
    """
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")

    today = timezone.now().date()

    # Fallback dates if not provided
    if not end_date:
        end_date = today
    if not start_date:
        start_date = end_date - timedelta(days=60)

    # Base queryset: convert weight_date string to date
    queryset = StockBalance.objects.annotate(
        weight_date_dt=ToFormalDate(F("weight_date"))
    ).filter(
        weight_date_dt__range=(start_date, end_date)
    )

    # Aggregate totals
    totals = queryset.aggregate(
        total_purchase_qty=Sum("purchased_qty"),
        total_purchase_value=Sum("purchased_value"),
        total_issue_qty=Sum("issued_qty"),
        total_issue_value=Sum("issue_value"),
    )

    # Ensure 0 instead of None for empty results
    totals = {k: v or 0 for k, v in totals.items()}

    # Fetch Beginning Balance
    beginning = BeginningBalance.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by("-created_at").first()

    beginning_qty = beginning.beginning_qty if beginning else 0
    beginning_value = beginning.beginning_value if beginning else 0

    totals["beginning_qty"] = beginning_qty
    totals["beginning_value"] = beginning_value

    # Include start and end date in response
    totals["start_date"] = start_date
    totals["end_date"] = end_date

    return {
        "totals": totals,
        "queryset": queryset
    }

def add_issue_balance(issue_date, issue_no, issue_weight, melting_plant, user):
    """
    Create a StockBalance record when a RawMaterialIssue is APPROVED.

    Rules:
    - Every issue creates a new StockBalance record
    - issue_no is unique
    - remaining_qty is calculated based on the latest balance
    """

    try:
        with transaction.atomic():

            # Get last stock balance for the plant
            last_balance = (
                StockBalance.objects
                .filter(
                    is_deleted=False
                )
                .order_by("-record_time")
                .first()
            )

            previous_remaining_qty = last_balance.remaining_qty if last_balance else 0
            previous_remaining_value = last_balance.remaining_value if last_balance else 0

            # Calculate new remaining quantity and value
            new_remaining_qty = previous_remaining_qty - issue_weight
            new_remaining_value = round(
                previous_remaining_value / previous_remaining_qty,
                2
            )

            # Create a new stock balance entry
            stock_balance = StockBalance.objects.create(
                transaction_type=StockBalanceOn.ISSUE.value,
                issue_no=issue_no,
                issued_qty=issue_weight,
                remaining_qty=new_remaining_qty,
                remaining_value=new_remaining_value,
                melting_plant=melting_plant,
                weight_date=issue_date,
                created_by=user,
                updated_by=user
            )

            serializer = StockBalanceSerializer(stock_balance)

            return {
                "stock_balance": serializer.data,
                "issued_qty": issue_weight,
                "previous_remaining_qty": previous_remaining_qty,
                "new_remaining_qty": new_remaining_qty
            }

    except Exception as e:
        logger.error(f"Error in add_issue_balance: {e}")
        raise e