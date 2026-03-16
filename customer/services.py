from django.db.models import Count, Sum

from customer.models import PurchaseCustomer


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