import json
import logging
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum, DateTimeField, F
from django.db.models.functions import Cast
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import permission_classes, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from helperFunctions.pagination import stock_balance_pagination
from helperFunctions.validations import ToDate
from stock.models import StockBalance, BeginningBalance
from stock.serializers import BeginningBalanceSerializer, StockBalanceFilterSerializer
from stock.services import create_beginning_balance, get_stock_balance_service
from stock.utils.date_format import _default_date_range, parse_date, convert_date_format
from utils.permissions import role_required

# Create your views here.
logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')
User = get_user_model()

@permission_classes([IsAuthenticated])
def add_purchase_stock(purchase_weight_data, request):
    """
    Update StockBalance records with purchase weights
    Uses transaction.atomic() for data consistency
    """
    saved_records = []

    with transaction.atomic():
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")

            active_cumulative_balance = BeginningBalance.objects.filter(
                is_active=True,
                is_deleted=False
            ).select_for_update().first()

            for date_key, values in purchase_weight_data.items():
                purchase_weight = float(values.get("purchase_weight", 0))
                transport_weight = float(values.get("transport_weight", 0))

                try:
                    date_key = convert_date_format(date_key)
                except ValueError:
                    logging.error(f"Skipping invalid date key: {date_key}")
                    continue

                stock, created = StockBalance.objects.get_or_create(
                    weight_date=date_key,
                    is_deleted=False,
                    defaults={
                        'purchase_weight': purchase_weight,
                        'transport_weight': transport_weight,
                        'issue_no': "",
                        'net_weight': purchase_weight - transport_weight,
                        'created_by': request.user.username,
                        'created_at': today_str,
                        'updated_by': request.user.username,
                        'updated_at': today_str,
                    }
                )

                if not created:
                    old_net_weight = stock.net_weight

                    stock.purchase_weight += purchase_weight
                    if transport_weight > 0:
                        stock.transport_weight += transport_weight

                    stock.net_weight = stock.purchase_weight - stock.transport_weight
                    stock.updated_by = request.user.username
                    stock.updated_at = today_str
                    stock.save()

                    # Update cumulative balance
                    if active_cumulative_balance:
                        net_weight_difference = stock.net_weight - old_net_weight
                        active_cumulative_balance.current_balance += net_weight_difference
                        active_cumulative_balance.save()

                    action = "updated"
                else:
                    if active_cumulative_balance:
                        active_cumulative_balance.current_balance += stock.net_weight
                        active_cumulative_balance.save()

                    action = "created"

                saved_records.append({
                    "action": action,
                    "stock_balance_id": str(stock._id),
                    "weight_date": stock.weight_date,
                    "purchase_weight": stock.purchase_weight,
                    "transport_weight": stock.transport_weight,
                    "net_weight": stock.net_weight,
                    "issue_no": stock.issue_no or "",
                    "cumulative_balance_updated": bool(active_cumulative_balance),
                    "cumulative_balance_current": float(active_cumulative_balance.current_balance) if active_cumulative_balance else 0
                })

            return saved_records

        except Exception as e:
            logger.error(f"Error in add_purchase_stock: {e}")
            raise e

@permission_classes([IsAuthenticated])
def add_transport_stock(transport_weight, request):
    saved_records = []
    active_cumulated_balance = BeginningBalance.objects.filter(is_active=True).first()
    for date_key, values in transport_weight.items():
        purchase_weight = float(values.get("purchase_weight", 0))
        transport_weight = float(values.get("transport_weight", 0))

        stock = StockBalance.objects.filter(weight_date=date_key).first()

        if stock:
            stock.transport_weight += transport_weight
            stock.net_weight = stock.purchase_weight - stock.transport_weight
            stock.updated_by = request.user.username
            stock.updated_at = today
            stock.save()

            if active_cumulated_balance:
                active_cumulated_balance.current_balance -= stock.net_weight
                active_cumulated_balance.save()
        else:
            stock = StockBalance.objects.create(
                purchase_weight=purchase_weight,
                transport_weight=transport_weight,
                net_weight=purchase_weight - transport_weight,
                weight_date=date_key,
                created_by=request.user.username,
                created_at=today,
                updated_by=request.user.username,
                updated_at=today
            )
            if active_cumulated_balance:
                active_cumulated_balance.current_balance -= stock.net_weight
                active_cumulated_balance.save()

        saved_records.append({
            "weight_date": stock.weight_date,
            "purchase_weight": stock.purchase_weight,
            "transport_weight": stock.transport_weight,
            "net_weight": stock.net_weight,
        })

    return saved_records

@permission_classes([IsAuthenticated])
def add_transport_balance(total_transport_weight, request, issue_date, issue_no):
    """
    Update StockBalance record when a raw material issue is approved

    Logic:
    1. Find the StockBalance record with weight_date == issue_date
    2. If found: update transport_weight, add issue_no to the issue_date field, recalculate net_weight
    3. If not found: create a new record with purchase_weight=0, net_weight=-total_transport_weight
    """
    try:
        active_cumulated_balance = BeginningBalance.objects.filter(is_active=True).first()
        # Convert issue_date to string if it's not already
        if isinstance(issue_date, datetime):
            issue_date_str = issue_date.strftime("%Y-%m-%d")
        else:
            issue_date_str = str(issue_date)

        stock_balance = StockBalance.objects.filter(
            weight_date=issue_date_str,
            is_deleted=False
        ).first()

        if stock_balance:
            stock_balance.transport_weight += total_transport_weight

            if stock_balance.issue_no:
                if issue_no not in stock_balance.issue_no:
                    stock_balance.issue_no = issue_no
            else:
                stock_balance.issue_no = issue_no

            stock_balance.net_weight = stock_balance.purchase_weight - stock_balance.transport_weight

            stock_balance.updated_by = request.user.username
            stock_balance.updated_at = today

            stock_balance.save()
            
            if active_cumulated_balance:
                active_cumulated_balance.current_balance -= abs(stock_balance.net_weight)
                active_cumulated_balance.save()

            return {
                "action": "updated",
                "stock_balance_id": str(stock_balance._id),
                "previous_transport_weight": stock_balance.transport_weight - total_transport_weight,
                "new_transport_weight": stock_balance.transport_weight,
                "new_net_weight": stock_balance.net_weight
            }

        else:
            stock_balance = StockBalance.objects.create(
                purchase_weight=0.0,
                transport_weight=total_transport_weight,
                issue_no=issue_no,
                net_weight=0 - total_transport_weight,
                weight_date=issue_date_str,
                created_by=request.user.username,
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                updated_by=request.user.username,
                updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            
            if active_cumulated_balance:
                active_cumulated_balance.current_balance -= abs(stock_balance.net_weight)
                active_cumulated_balance.save()

            return {
                "action": "created",
                "stock_balance_id": str(stock_balance._id),
                "transport_weight": stock_balance.transport_weight,
                "net_weight": stock_balance.net_weight
            }

    except Exception as e:
        logger.error(f"Error in add_transport_balance: {e}")
        raise e

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def add_beginning_balance(request):
    serializer = BeginningBalanceSerializer(data=request.data)

    if not serializer.is_valid():
        return JsonResponse(
            {
                "result": "error",
                "message": "Invalid input",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validated_data = serializer.validated_data
        beginning_qty = validated_data["beginning_qty"]
        beginning_value = validated_data["beginning_value"]

        # Use the helper function
        new_balance = create_beginning_balance(beginning_qty, beginning_value, request.user)

        return JsonResponse(
            {
                "result": "success",
                "message": "Beginning balance added successfully",
                "content": {
                    "id": str(new_balance._id),
                    "beginning_qty": new_balance.beginning_qty,
                    "beginning_value": new_balance.beginning_value,
                    "current_qty": new_balance.current_qty,
                    "current_value": new_balance.current_value,
                    "is_active": new_balance.is_active,
                    "created_by": new_balance.created_by.username if new_balance.created_by else None,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        logger.error("Error occurred while creating beginning balance: %s", str(e))
        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while creating beginning balance",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_balance_summary(request):
    try:
        active_balance = BeginningBalance.objects.filter(
            is_active=True
        ).first()

        if not active_balance:
            return JsonResponse(
                {
                    "result": "success",
                    "message": "No active balance found.",
                    "content": {}
                },
                status=status.HTTP_200_OK
            )

        stock_records = StockBalance.objects.annotate(
            weight_date_dt=ToDate(F("weight_date"))
        ).filter(
            weight_date_dt__gte=active_balance.created_at
        ).aggregate(
            total_purchase=Sum("purchased_qty"),
            total_purchase_value=Sum("purchased_value"),
            total_issue=Sum("issued_qty"),
            total_issue_value=Sum("issue_value")
        )

        total_purchase = stock_records["total_purchase"] or 0.0
        total_purchase_value = stock_records["total_purchase_value"] or 0.0
        total_issue = stock_records["total_issue"] or 0.0
        total_issue_value = stock_records["total_issue_value"] or 0.0

        return JsonResponse(
            {
                "result": "success",
                "active_balance": {
                    "_id": str(active_balance._id),
                    "created_by": active_balance.created_by.username if active_balance.created_by else None,
                    "created_at": active_balance.created_at,
                    "beginning_qty": active_balance.beginning_qty,
                    "beginning_value": active_balance.beginning_value,
                    "current_qty": active_balance.current_qty,
                    "current_value": active_balance.current_value,
                },
                "totals": {
                    "total_purchase_qty": total_purchase,
                    "total_purchase_value": total_purchase_value,
                    "total_issued_qty": total_issue,
                    "total_issued_value": total_issue_value,
                }
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error("Error while fetching active balance summary: %s", str(e))

        return JsonResponse(
            {
                "result": "error",
                "message": "An error occurred while fetching the summary."
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_stock_balance(request):
    """
    Fetch stock balance records filtered by type and date range.
    Delegates all business logic to get_stock_balance_service.
    """
    try:
        serializer = StockBalanceFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # 2. Fetch queryset from service
        queryset = get_stock_balance_service(serializer.validated_data)

        # 3. Paginate results
        paginated_records = stock_balance_pagination(request, queryset)

        # 4. Return response
        return JsonResponse(
            {
                "result": "success",
                "message": "Stock balance records fetched successfully",
                "data": paginated_records.data
            },
            status=status.HTTP_200_OK
        )

    except ValidationError as e:
        logger.error("Validation error: %s", str(e))
        return JsonResponse(
            {
                "result": "error",
                "message": "Validation error",
                "errors": e.detail
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error("Error occurred while fetching stock balance: %s", str(e))
        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while fetching stock balance"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def generate_stock_report(start_date: str = "", end_date: str = "", report_type: str = "all") -> dict:
    if report_type not in {"all", "purchase", "transport"}:
        raise ValueError("report_type must be 'all', 'purchase', or 'transport'")

    if not start_date and not end_date:
        start_date, end_date = _default_date_range()
    elif not start_date:
        start_date, _ = _default_date_range()
    elif not end_date:
        _, end_date = _default_date_range()

    start_dt = parse_date(start_date)
    end_dt = parse_date(end_date)

    qs = StockBalance.objects.filter(
        is_deleted=False,
        weight_date__range=[start_date, end_date],
    ).order_by('weight_date')

    records = []
    for stock in qs:
        records.append({
            "weight_date": stock.weight_date,
            "purchase": float(stock.purchase_weight),
            "transport": float(stock.transport_weight),
            "net": float(stock.net_weight),
            "issue_no": stock.issue_no or "",
        })

    agg = StockBalance.objects.filter(
        is_deleted=False,
        weight_date__gte=start_date,
        weight_date__lte=end_date
    ).aggregate(
        purchase_agg=Sum("purchase_weight", default=0.0),
        transport_agg=Sum("transport_weight", default=0.0),
        net_agg=Sum("net_weight", default=0.0),
    )

    if report_type == "all":
        balances = {
            "records": records,
            "purchase_aggregation": float(agg["purchase_agg"] or 0),
            "transport_aggregation": float(agg["transport_agg"] or 0),
            "net_aggregation": float(agg["net_agg"] or 0),
        }
    elif report_type == "purchase":
        balances = {
            "records": records,
            "purchase_aggregation": float(agg["purchase_agg"] or 0),
        }
    else:  # transport
        balances = {
            "records": records,
            "transport_aggregation": float(agg["transport_agg"] or 0),
        }

    # Get cumulative balance
    active = BeginningBalance.objects.filter(
        is_active=True, is_deleted=False
    ).first()

    beginning = float(active.beginning_balance) if active else 0.0
    current = float(active.current_balance) if active else 0.0

    return {
        "type": report_type,
        "start_date": start_date,
        "end_date": end_date,
        "balances": balances,
        "beginning_balance": beginning,
        "current_balance": current,
        "total_records": len(records),
    }

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_stock_report(request):
    data = json.loads(request.body)
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    report_type = data.get("report_type")
    try:
        report = generate_stock_report(start_date, end_date, report_type)
        return JsonResponse({"result": "success", "message": "Report is generated successfully.", "content": report}, status=200)
    except ValueError as e:
        logger.error("Error occurred while generating stock report: %s", e)
        return JsonResponse({"result": "error", 'message': "Error occurred while generating report."}, status=400)

def generate_stock_card(start_date: str = "", end_date: str = "") -> dict:
    if not start_date and not end_date:
        start_date, end_date = _default_date_range()
    elif not start_date:
        start_date, _ = _default_date_range()
    elif not end_date:
        _, end_date = _default_date_range()

    start_dt = parse_date(start_date)
    end_dt = parse_date(end_date)

    qs = StockBalance.objects.filter(
        is_deleted=False,
        weight_date__gte=start_date,
        weight_date__lte=end_date,
    ).order_by('weight_date')

    stock_card = []
    total_purchase_weight = 0.0
    total_transport_weight = 0.0
    running_balance = 0.0

    for stock in qs:
        if not stock.weight_date:
            continue
        try:
            weight_date_str = datetime.strptime(stock.weight_date, '%Y-%m-%d').strftime('%d.%m.%Y')
        except ValueError:
            weight_date_str = stock.weight_date

        purchase_weight = float(stock.purchase_weight or 0)
        transport_weight = float(stock.transport_weight or 0)
        daily_balance = float(stock.net_weight or 0)

        total_purchase_weight += purchase_weight
        total_transport_weight += transport_weight
        running_balance += daily_balance

        stock_card.append({
            "weight_date": weight_date_str,
            "GRN No": "-",
            "Issue Voucher NO": stock.issue_no or "-",
            "purchase_weight": round(purchase_weight, 2),
            "transport_weight": round(transport_weight, 2),
            "balance": round(daily_balance, 2)
        })

    # Summary
    summary = {
        "total_purchase_weight": round(total_purchase_weight, 2),
        "total_transport_weight": round(total_transport_weight, 2),
        "Balance": round(running_balance, 2)
    }

    return {
        "stock_card": stock_card,
        "summary": summary
    }

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_stock_card(request):
    data = json.loads(request.body)
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    try:
        report = generate_stock_card(start_date, end_date)
        return JsonResponse({"result": "success", "message": "Stock card is generated successfully.", "content": report}, status=200)
    except ValueError as e:
        logger.error("Error occurred while generating stock card: %s", e)
        return JsonResponse({"result": "error", 'message': "Error occurred while generating stock card."}, status=400)

