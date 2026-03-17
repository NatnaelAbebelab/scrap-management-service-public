import string, logging
from calendar import month_abbr
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum, FloatField, Count, F, Q, Func, CharField
from django.db.models.functions import Cast, TruncDay, TruncWeek, TruncMonth, TruncYear, Round, TruncQuarter, \
    ExtractYear, ExtractQuarter
from django.utils import timezone

from customer.models import PurchaseCustomer
from grn.models import GRN
from helperFunctions.date_manipulation import get_last_week
from helperFunctions.formatter import format_large_number
from helperFunctions.material_type import MaterialType
from helperFunctions.status import Status
from helperFunctions.validations import ToDateTime, ToDate, ToFormalDate
from internal.models import DailyScrapMoveAggregate, Agency

logger = logging.getLogger(__name__)

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

def internal_aggregate_report(
    queryset,
    period="daily",
    by_tin=False,
    by_material_type=False,
    by_start_date=False,
    by_end_date=False,
    by_status=False,
    start_date=None,
    end_date=None
):
    """
    Generic internal aggregation report (daily/weekly/monthly/yearly/quarterly)
    """
    PERIOD_CONFIG = {
        "daily": {
            "trunc": TruncDay,
            "format": "Mon DD, YYYY"
        },
        "weekly": {
            "trunc": TruncWeek,
            "format": "Mon DD, YYYY"
        },
        "monthly": {
            "trunc": TruncMonth,
            "format": "Mon YYYY"
        },
        "quarterly": {
            "trunc": TruncQuarter,
            "format": None
        },
        "yearly": {
            "trunc": TruncYear,
            "format": "YYYY"
        }
    }

    config = PERIOD_CONFIG.get(period, PERIOD_CONFIG["daily"])

    # Annotate period
    queryset = queryset.annotate(
        period=config["trunc"]("casted_weight_date")
    )

    # Extract base values (only once)
    base_row = queryset.values("TIN", "material_type", "status").first()

    tin = base_row["TIN"] if base_row else None
    material_type = base_row["material_type"] if base_row else None
    _status = base_row["status"] if base_row else None

    exists = queryset.exists()

    # Build extra info
    extra_info = {}

    if by_tin and exists:
        agency = Agency.objects.filter(TIN=tin).first()
        if agency:
            extra_info["agency_info"] = {
                "first_name": string.capwords(agency.first_name),
                "last_name": string.capwords(agency.last_name),
                "TIN": agency.TIN,
                "business_name": string.capwords(agency.business_name)
            }

    if by_material_type and exists:
        extra_info["material_type"] = {
            "name": MaterialType.get_material_type(material_type)
        }

    if by_start_date:
        extra_info["start_date_info"] = {"start_date": start_date}

    if by_end_date:
        extra_info["end_date_info"] = {"end_date": end_date}

    if by_status and exists:
        extra_info["status_info"] = {
            "status": Status.get_status(_status).name
        }

    # Aggregation
    report_data = queryset.values("period").annotate(
        total_quantity=Count("_id"),
        total_net_weight=Round(Sum(Cast("daily_net_weight", FloatField())), 2),
        total_net_price=Round(Sum(Cast("net_price", FloatField())), 2),
        record_count=Count("_id"),
    ).order_by("period")

    # Handle quarterly separately
    if period == "quarterly":
        report_data = report_data.annotate(
            year=ExtractYear("period"),
            quarter=ExtractQuarter("period")
        )

        data = list(report_data.values(
            "total_net_weight",
            "total_net_price",
            "period",
            "record_count",
            "year",
            "quarter"
        ))

        # Format in Python
        for row in data:
            row["formatted_period"] = f"Q{row['quarter']} {row['year']}"

    else:
        # Default formatting using TO_CHAR
        report_data = report_data.annotate(
            formatted_period=Func(
                F("period"),
                function="TO_CHAR",
                template=f"%(function)s(%(expressions)s, '{config['format']}')",
                output_field=CharField()
            )
        )

        data = list(report_data.values(
            "total_net_weight",
            "total_net_price",
            "period",
            "formatted_period",
            "record_count"
        ))

    return {
        "data": data,
        "extra_info": extra_info
    }

def internal_process_report_service(filters):
    """
    Internal process report generator
    """
    try:
        tin = filters.get("tin")
        material_type = filters.get("material_type")
        plate_no = filters.get("plate_no")
        start_date = filters.get("start_date")
        end_date = filters.get("end_date")
        status = filters.get("status")
        period = filters.get("period")

        queryset = (
            DailyScrapMoveAggregate.objects
            .filter(is_deleted=False)
            .annotate(casted_weight_date=ToDateTime(F("weight_date")))
            .order_by("-record_time")
        )

        query_filter = Q()

        # TIN filter (avoid unnecessary DB hit)
        if tin:
            query_filter &= Q(TIN=tin)

        # Material type
        if material_type:
            query_filter &= Q(material_type__iexact=material_type)

        # Plate number (ensure field exists in model)
        if plate_no:
            query_filter &= Q(plate_no__iexact=plate_no)

        # Date filters
        if start_date:
            query_filter &= Q(casted_weight_date__gte=start_date)

        if end_date:
            query_filter &= Q(casted_weight_date__lte=end_date)

        # Status filter
        if status:
            query_filter &= Q(status__iexact=status)

        queryset = queryset.filter(query_filter)

        # Aggregation mapping (NOW includes quarterly)
        aggregation_map = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly",
            "quarterly": "quarterly",
            "yearly": "yearly",
        }

        period_key = aggregation_map.get(period, "daily")

        # Generate a report
        result = internal_aggregate_report(
            queryset=queryset,
            period=period_key,
            by_tin=bool(tin),
            by_material_type=bool(material_type),
            by_start_date=bool(start_date),
            by_end_date=bool(end_date),
            by_status=bool(status),
            start_date=start_date,
            end_date=end_date
        )

        return result

    except Exception as e:
        logger.error("Error occurred while aggregating scrap move: %s", e)
        raise Exception("Error occurred while aggregating records")

def internal_general_metrics_service(start_date=None, end_date=None):
    """
    Generate internal general metrics
    """
    try:
        queryset = DailyScrapMoveAggregate.objects.annotate(
            casted_weight_date=ToFormalDate("weight_date")
        )

        # Apply date filters
        if start_date:
            queryset = queryset.filter(casted_weight_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(casted_weight_date__lte=end_date)

        # Weekly scrap moves (filtered)
        weekly_scrap_move = queryset.count()

        # Global metrics (use base queryset only once)
        base_qs = DailyScrapMoveAggregate.objects.all()

        total_agencies = Agency.objects.count()
        total_daily_scrap_moves = base_qs.count()

        total_approved_daily_scrap_moves = base_qs.filter(
            status=Status.APPROVED.status_value
        ).count()

        paid_data = base_qs.filter(
            status=Status.PAID.status_value
        ).aggregate(
            total_net_price=Sum(Cast("net_price", FloatField())),
            record_count=Count("_id")
        )

        total_paid_daily_scrap_moves_count = paid_data.get("record_count") or 0

        total_paid_amount = paid_data.get("total_net_price") or 0
        total_paid_amount = Decimal(str(total_paid_amount)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return {
            "weekly_scrap_move": weekly_scrap_move,
            "total_agencies": total_agencies,
            "total_daily_scrap_moves": total_daily_scrap_moves,
            "total_approved_daily_scrap_moves": total_approved_daily_scrap_moves,
            "total_paid_daily_scrap_moves_count": total_paid_daily_scrap_moves_count,
            "total_paid_amount": total_paid_amount,
        }

    except Exception as e:
        logger.error("Error occurred while generating general metrics: %s", e)
        raise Exception("Error occurred while generating general metrics")

def yearly_internal_scrap_move_service():
    """
    Yearly internal scrap move aggregated by month
    """
    try:
        now = timezone.now()
        start_date = (now - timedelta(days=365)).replace(day=1)
        end_date = now

        queryset = (
            DailyScrapMoveAggregate.objects
            .annotate(casted_weight_date=ToFormalDate("weight_date"))
            .filter(
                casted_weight_date__range=(start_date, end_date),
                material_type__iexact=MaterialType.SCRAP.value
            )
            .order_by("record_time")
        )

        # Use unified aggregation (monthly)
        result = internal_aggregate_report(
            queryset=queryset,
            period="monthly",
            by_material_type=True,
            start_date=start_date,
            end_date=end_date
        )

        formatted_result = {}

        for row in result.get("data", []):
            period = row["period"]
            month = period.month
            year = period.year
            month_name = month_abbr[month].lower()

            total_net_price = Decimal(str(row["total_net_price"] or 0)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            total_net_weight = Decimal(str(row["total_net_weight"] or 0)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            formatted_result[month_name] = {
                "month": month_name,
                "year": year,
                "total_net_price": float(total_net_price),
                "total_net_weight": float(total_net_weight),
                "format_total_net_price": format_large_number(total_net_price),
                "format_net_weight": format_large_number(total_net_weight),
            }

        return formatted_result

    except Exception as e:
        logger.error("Error occurred while generating yearly report: %s", e)
        raise Exception("Error occurred while generating yearly report")