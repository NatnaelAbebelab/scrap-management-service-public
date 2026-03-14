from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum, FloatField, Count, F
from django.db.models.functions import Cast, TruncDay, TruncWeek, TruncMonth, TruncYear
from django.utils import timezone

from customer.models import PurchaseCustomer
from grn.models import GRN
from helperFunctions.date_manipulation import get_last_week
from helperFunctions.formatter import format_large_number
from helperFunctions.material_type import MaterialType
from helperFunctions.status import Status
from helperFunctions.validations import ToDateTime, ToDate


def generate_grn_plain_report(filters):

    queryset = GRN.objects.filter(is_deleted=False)

    tin = filters.get("tin")
    status = filters.get("status")
    material_type = filters.get("material_type")
    plate_no = filters.get("plate_no")
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")

    if tin:
        queryset = queryset.filter(customer__icontains=tin)

    if status:
        queryset = queryset.filter(status=status)

    if material_type:
        queryset = queryset.filter(material_type=material_type)

    if plate_no:
        queryset = queryset.filter(plate_no__icontains=plate_no)

    if start_date:
        queryset = queryset.annotate(
            first_date_dt=ToDate("first_date")
        ).filter(
            first_date_dt__gte=start_date
        )

    if end_date:
        queryset = queryset.annotate(
            first_date_dt=ToDate("first_date")
        ).filter(
            first_date_dt__lte=end_date
        )

    totals = queryset.aggregate(
        total_net_price=Sum(Cast("net_price", FloatField())),
        total_net_weight=Sum(Cast("net_weight", FloatField())),
        total_records=Count("_id")
    )

    return queryset.order_by("-record_time"), totals

def generate_grn_aggregate_report_service(filters):

    queryset = GRN.objects.filter(is_deleted=False)

    tin = filters.get("tin")
    material_type = filters.get("material_type")
    plate_no = filters.get("plate_no")
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")
    status = filters.get("status")
    period = filters.get("period")

    # ---------------- Filters ----------------

    if tin:
        queryset = queryset.filter(customer__icontains=tin)

    if material_type:
        queryset = queryset.filter(material_type__iexact=material_type)

    if plate_no:
        queryset = queryset.filter(plate_no__iexact=plate_no)

    if status:
        queryset = queryset.filter(status__iexact=status)

    # Date filter using first_date
    queryset = queryset.annotate(
        first_date_dt=ToDate(F("first_date"))
    )

    if start_date:
        queryset = queryset.filter(first_date_dt__gte=start_date)

    if end_date:
        queryset = queryset.filter(first_date_dt__lte=end_date)

    # ---------------- Period Aggregation ----------------

    if period == "daily":
        queryset = queryset.annotate(period_date=TruncDay("first_date_dt"))
    elif period == "weekly":
        queryset = queryset.annotate(period_date=TruncWeek("first_date_dt"))
    elif period == "monthly":
        queryset = queryset.annotate(period_date=TruncMonth("first_date_dt"))
    elif period == "quarterly":
        queryset = queryset.annotate(period_date=TruncMonth("first_date_dt"))
    elif period == "yearly":
        queryset = queryset.annotate(period_date=TruncYear("first_date_dt"))

    aggregated = (
        queryset.values("period_date")
        .annotate(
            total_net_weight=Sum(Cast("net_weight", FloatField())),
            total_net_price=Sum(Cast("net_price", FloatField())),
            total_records=Count("_id"),
        )
        .order_by("period_date")
    )

    # ---------------- Footer Totals ----------------

    totals = queryset.aggregate(
        total_net_weight=Sum(Cast("net_weight", FloatField())),
        total_net_price=Sum(Cast("net_price", FloatField())),
        total_records=Count("_id"),
    )

    return list(aggregated), totals

def generate_general_metrics():

    start_date, end_date = get_last_week()

    # Base queryset (avoid repeating table scans)
    grn_queryset = GRN.objects.annotate(
        first_date_dt=ToDateTime("first_date")
    )

    # Weekly purchases
    weekly_purchase_qs = grn_queryset
    if start_date:
        weekly_purchase_qs = weekly_purchase_qs.filter(first_date_dt__gte=start_date)
    if end_date:
        weekly_purchase_qs = weekly_purchase_qs.filter(first_date_dt__lte=end_date)

    weekly_purchase = weekly_purchase_qs.count()

    # Totals (single queries each — acceptable for metrics)
    total_vendors = PurchaseCustomer.objects.count()
    total_grn = GRN.objects.count()
    total_approved_grn = GRN.objects.filter(
        status=Status.APPROVED.status_value
    ).count()

    total_paid_data = GRN.objects.filter(
        status=Status.PAID.status_value
    ).aggregate(
        total_net_price=Sum(Cast("net_price", FloatField())),
        record_count=Count("_id")
    )

    total_paid_grn = total_paid_data.get("record_count") or 0

    total_paid_amount_raw = total_paid_data.get("total_net_price")
    total_paid_amount = (
        Decimal(str(total_paid_amount_raw)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )
        if total_paid_amount_raw is not None
        else Decimal("0.00")
    )

    return {
        "weekly_purchase": weekly_purchase,
        "total_vendors": total_vendors,
        "total_grn": total_grn,
        "total_approved_grn": total_approved_grn,
        "total_paid_grn": total_paid_grn,
        "total_paid_amount": total_paid_amount,
        "weekly_purchase_text": format_large_number(weekly_purchase),
        "total_vendors_text": format_large_number(total_vendors),
        "total_grn_text": format_large_number(total_grn),
        "total_approved_grn_text": format_large_number(total_approved_grn),
        "total_paid_grn_text": format_large_number(total_paid_grn),
        "total_paid_amount_text": format_large_number(total_paid_amount),
    }

def generate_scrap_grade_percentage():

    queryset = GRN.objects.filter(
        material_type__iexact=MaterialType.SCRAP.value
    )

    aggregation = queryset.aggregate(
        heavy_sum=Sum(Cast("heavy_grade", FloatField())),
        medium_sum=Sum(Cast("medium_grade", FloatField())),
        light_sum=Sum(Cast("light_grade", FloatField())),
    )

    heavy_sum = aggregation["heavy_sum"] or 0
    medium_sum = aggregation["medium_sum"] or 0
    light_sum = aggregation["light_sum"] or 0

    total_weight = heavy_sum + medium_sum + light_sum

    if total_weight == 0:
        return {"H": Decimal("0.00"), "M": Decimal("0.00"), "L": Decimal("0.00")}

    percentage = {
        "H": Decimal((heavy_sum / total_weight) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        "M": Decimal((medium_sum / total_weight) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        "L": Decimal((light_sum / total_weight) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
    }

    return percentage

def generate_yearly_purchase_report():

    now = timezone.now()

    # Last 12 months
    start_date = (now - timedelta(days=365)).date()
    end_date = now.date()

    queryset = (
        GRN.objects.annotate(
            first_date_dt=ToDateTime("first_date"),
            period=TruncMonth("first_date_dt"),
        )
        .filter(
            first_date_dt__range=(start_date, end_date),
            material_type__iexact=MaterialType.SCRAP.value,
        )
    )

    monthly_data = (
        queryset.values("period")
        .annotate(
            total_net_price=Sum(Cast("net_price", FloatField())),
            total_net_weight=Sum(Cast("net_weight", FloatField())),
        )
        .order_by("period")
    )

    formatted_result = {}

    for item in monthly_data:
        period = item["period"]

        total_net_price = Decimal(item["total_net_price"] or 0).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        total_net_weight = Decimal(item["total_net_weight"] or 0).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        month_name = period.strftime("%b").lower()  # jan, feb, etc.

        formatted_result[month_name] = {
            "month": month_name,
            "year": period.year,
            "total_net_price": total_net_price,
            "total_net_weight": total_net_weight,
            "format_total_net_price": format_large_number(total_net_price),
            "format_net_weight": format_large_number(total_net_weight),
        }

    return formatted_result