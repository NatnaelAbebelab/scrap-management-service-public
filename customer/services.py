from decimal import Decimal

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404

from customer.models import PurchaseCustomer
from grn.models import GRN


def generate_purchase_customer_plain_report(filters: dict):
    """
    Generate Purchase Customer Plain Report filtered by TIN
    """

    tin = filters.get("tin")

    queryset = PurchaseCustomer.objects.all()

    if tin:
        queryset = queryset.filter(TIN__icontains=tin)

    queryset = queryset.order_by("-record_time")

    totals = queryset.aggregate(
        total_customers=Count("_id"),
        total_paid_amount=Sum("paid_amount"),
        total_remaining_amount=Sum("remaining_amount"),
    )

    records = list(
        queryset.values(
            "_id",
            "first_name",
            "last_name",
            "business_name",
            "phone",
            "email",
            "TIN",
            "paid_amount",
            "remaining_amount",
            "created_at",
        )
    )

    return {
        "totals": totals,
        "records": records,
        "queryset": queryset
    }

def generate_purchase_customer_aggregated_report(filters: dict):
    """
    Generate an aggregated customer report grouped by TIN
    """

    tin = filters.get("tin")

    queryset = PurchaseCustomer.objects.all()

    if tin:
        queryset = queryset.filter(TIN__icontains=tin)

    queryset = queryset.order_by("-record_time")

    aggregated_queryset = (
        queryset
        .values("TIN")
        .annotate(
            customer_count=Count("_id"),
            total_paid_amount=Sum("paid_amount"),
            total_remaining_amount=Sum("remaining_amount"),
        )
    )

    totals = queryset.aggregate(
        total_customers=Count("_id"),
        total_paid_amount=Sum("paid_amount"),
        total_remaining_amount=Sum("remaining_amount"),
    )

    return {
        "records": list(aggregated_queryset),
        "totals": totals,
        "queryset": aggregated_queryset
    }

def get_grn_by_tin_and_status(tin: str, status: str):
    return GRN.objects.filter(
        customer=tin,
        status=status,
        is_deleted=False
    ).values("record_no", "net_price")

def get_customer_net_pay_summary(tin: str, record_numbers: list):

    customer = get_object_or_404(
        PurchaseCustomer.objects.only(
            "first_name", "last_name", "business_name", "TIN"
        ),
        TIN=tin,
        is_deleted=False
    )

    grn = GRN.objects.filter(
        customer=tin,
        record_no__in=record_numbers,
        is_deleted=False
    ).values(
        "record_no",
        "grn_no",
        "serial_no",
        "first_date",
        "first_weight",
        "heavy_grade",
        "medium_grade",
        "light_grade",
        "heavy_rate",
        "medium_rate",
        "light_rate",
        "net_price"
    )

    grn_list = list(grn)

    sub_total = sum(Decimal(g["net_price"] or 0) for g in grn_list)

    vat_price = sub_total * Decimal("0.15")
    grand_total = sub_total + vat_price
    with_holding_price = sub_total * Decimal("0.03")
    net_pay = grand_total - with_holding_price

    return {
        "customer_info": {
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "business_name": customer.business_name,
            "tin": customer.TIN,
        },
        "grn": grn_list,
        "calculated_price": {
            "sub_total": sub_total,
            "vat_price": vat_price,
            "grand_total": grand_total,
            "with_holding_price": with_holding_price,
            "net_pay": net_pay,
        }
    }