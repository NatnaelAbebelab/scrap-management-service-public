import logging
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db.models import Sum, F
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import permission_classes, api_view
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from helperFunctions.pagination import stock_balance_pagination
from helperFunctions.validations import ToDate
from stock.models import StockBalance, BeginningBalance
from stock.serializers import BeginningBalanceSerializer, StockBalanceFilterSerializer, \
    StockBalanceAggregatedReportSerializer, StockCardFilterSerializer, StockBalanceSerializer
from stock.services import create_beginning_balance, get_stock_balance_service, get_stock_balance_aggregated_service, \
    generate_stock_card_service
from stock.utils.date_format import _default_date_range, parse_date
from utils.permissions import role_required

# Create your views here.
logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')
User = get_user_model()

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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stock_balance_aggregated_report(request):
    try:
        serializer = StockBalanceAggregatedReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        aggregated_data = get_stock_balance_aggregated_service(serializer.validated_data)

        return JsonResponse({
            "result": "success",
            "message": "Stock balance aggregated report fetched successfully",
            "data": list(aggregated_data)  # QuerySet.values() → list
        }, status=status.HTTP_200_OK)

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
        logger.error("Error occurred while fetching stock balance aggregated report: %s", str(e))

        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while fetching stock balance aggregated report"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
    serializer = StockCardFilterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    filters = serializer.validated_data

    try:
        result = generate_stock_card_service(filters)
        totals = result["totals"]
        queryset = result["queryset"]

        serializer = StockBalanceSerializer(queryset, many=True)

        return JsonResponse({
            "result": "success",
            "message": "Stock card generated successfully.",
            "content": {
                "totals": totals,
                "stock_card": serializer.data
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error generating stock card: %s", e)
        return JsonResponse({
            "result": "error",
            "message": "An error occurred while generating stock card."
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

