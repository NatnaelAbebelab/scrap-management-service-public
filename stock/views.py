import logging
from datetime import datetime, timedelta
from typing import List, Dict

from django.db.models import Sum, DateField, Value
from django.db.models.functions import Cast, Concat, Substr
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import permission_classes, api_view
from rest_framework.permissions import IsAuthenticated

from grn.models import GRN
from helperFunctions.pagination import stock_balance_pagination
from internal.models import DailyScrapMoveAggregate
from stock.models import StockBalance, CumulativeBalance
from stock.utils.date_format import _default_date_range, parse_date
from utils.permissions import role_required
import json
# Create your views here.
logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')

@permission_classes([IsAuthenticated])
def add_purchase_stock(purchase_weight, request):
    saved_records = []
    active_cumulated_balance = CumulativeBalance.objects.filter(is_active=True).first()
    for date_key, values in purchase_weight.items():
        purchase_weight = float(values.get("purchase_weight", 0))
        transport_weight = float(values.get("transport_weight", 0))

        stock = StockBalance.objects.filter(weight_date=date_key).first()

        if stock:
            stock.purchase_weight += purchase_weight
            stock.net_weight = stock.purchase_weight - stock.transport_weight
            stock.updated_by = request.user.username
            stock.updated_at = today
            stock.save()
            if active_cumulated_balance:
                active_cumulated_balance.current_balance += stock.net_weight
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
                active_cumulated_balance.current_balance += stock.net_weight
                active_cumulated_balance.save()

        saved_records.append({
            "weight_date": stock.weight_date,
            "purchase_weight": stock.purchase_weight,
            "transport_weight": stock.transport_weight,
            "net_weight": stock.net_weight,
        })

    return saved_records

@permission_classes([IsAuthenticated])
def add_transport_stock(transport_weight, request):
    saved_records = []
    active_cumulated_balance = CumulativeBalance.objects.filter(is_active=True).first()
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
    if request.method == "POST":
        data = json.loads(request.body)
        try:
            beginning_balance_value = float(data.get("beginning_balance"))
            active_cumulated_balance = CumulativeBalance.objects.filter(is_active=True).first()
            if active_cumulated_balance:
                active_cumulated_balance.is_active = False
                active_cumulated_balance.save()

            beginning_balance_obj = CumulativeBalance.objects.create(
                beginning_balance=beginning_balance_value,
                current_balance=beginning_balance_value,
                is_active=True,
                created_by=request.user.username,
                created_at=today,
                updated_by=request.user.username,
                updated_at=today
            )
            return JsonResponse({
                "result": "success",
                "message": "Beginning balance added successfully",
                "content": {
                    "id": beginning_balance_obj._id,
                    "beginning_balance": beginning_balance_obj.beginning_balance,
                    "current_balance": beginning_balance_obj.current_balance,
                    "is_active": beginning_balance_obj.is_active,
                    "created_by": beginning_balance_obj.created_by,
                }
            }, status=status.HTTP_200_OK)


        except Exception as e:
            logger.error("Error occurred while creating beginning balance: %s", e)
            return JsonResponse({
                "result": "error",
                "message": "Error occurred while creating beginning balance",
            }, status=status.HTTP_400_BAD_REQUEST)
    return None

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_balance_summary(request):
    try:
        active_balance = CumulativeBalance.objects.filter(is_active=True, is_deleted=False).first()
        if not active_balance:
            return {"result": "error", "message": "No active cumulative balance found"}

        start_date = datetime.strptime(active_balance.created_at, "%Y-%d-%m").date()

        total_purchase = 0.0
        total_transport = 0.0

        stock_records = StockBalance.objects.all()

        for stock in stock_records:
            try:
                weight_date = datetime.strptime(stock.weight_date, "%d.%m.%Y").date()
                if weight_date >= start_date:
                    total_purchase += stock.purchase_weight
                    total_transport += stock.transport_weight
            except ValueError:
                continue

        response_data = {
            "result": "success",
            "active_balance": {
                "_id": str(active_balance._id),
                "created_by": active_balance.created_by,
                "created_at": active_balance.created_at,
                "current_balance": active_balance.current_balance,
            },
            "totals": {
                "total_purchase_weight": total_purchase,
                "total_transport_weight": total_transport,
            }
        }

        return JsonResponse(response_data, status=200)

    except Exception as e:
        logger.error("Error while fetching active balance summary: %s", e)
        return JsonResponse({
            "result": "error",
            "message": "An error occurred while fetching the summary."
        }, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_stock_balance(request):
    try :
        stock_balance = StockBalance.objects.all().order_by("-record_time")
        paginated_records = stock_balance_pagination(request, stock_balance)
        return JsonResponse({
            "result": "success",
            "data": paginated_records.data,
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "data": e
        }, status=status.HTTP_400_BAD_REQUEST)


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

    qs = (
        StockBalance.objects
        .annotate(
            weight_date_parsed=Cast(
                Concat(
                    Substr('weight_date', 7, 4), Value('-'),
                    Substr('weight_date', 4, 2), Value('-'),
                    Substr('weight_date', 1, 2)
                ),
                output_field=DateField()
            )
        )
        .filter(
            is_deleted=False,
            weight_date_parsed__gte=start_dt,
            weight_date_parsed__lte=end_dt,
        )
        .values(
            'weight_date',
            'purchase_weight',
            'transport_weight',
            'net_weight',
        )
        .order_by('weight_date_parsed')
    )
    records = [
        {
            "weight_date": item["weight_date"],
            "purchase": item["purchase_weight"],
            "transport": item["transport_weight"],
            "net": item["net_weight"],
        }
        for item in qs
    ]
    agg = (
        StockBalance.objects
        .annotate(weight_date_parsed=Cast(
            Concat(
                Substr('weight_date', 7, 4), Value('-'),
                Substr('weight_date', 4, 2), Value('-'),
                Substr('weight_date', 1, 2)
            ),
            output_field=DateField()
        ))
        .filter(is_deleted=False,
                weight_date_parsed__gte=start_dt,
                weight_date_parsed__lte=end_dt)
        .aggregate(
            purchase_agg=Sum("purchase_weight", default=0.0),
            transport_agg=Sum("transport_weight", default=0.0),
            net_agg=Sum("net_weight", default=0.0),
        )
    )
    if report_type == "all":
        balances = {
            "records": records,
            "purchase_aggregation": agg["purchase_agg"],
            "transport_aggregation": agg["transport_agg"],
            "net_aggregation": agg["net_agg"],
        }
    elif report_type == "purchase":
        balances = {
            "records": records,
            "purchase_aggregation": agg["purchase_agg"],
        }
    else:
        balances = {
            "records": records,
            "transport_aggregation": agg["transport_agg"],
        }
    active = (
        CumulativeBalance.objects
        .filter(is_active=True, is_deleted=False)
        .values("beginning_balance", "current_balance")
        .first()
    )
    beginning = active["beginning_balance"] if active else 0.0
    current = active["current_balance"] if active else 0.0

    return {
        "type": report_type,
        "start_date": start_dt.strftime("%d.%m.%Y"),
        "end_date": end_dt.strftime("%d.%m.%Y"),
        "balances": balances,
        "beginning_balance": beginning,
        "current_balance": current,
    }

@api_view(['GET'])
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

def generate_stock_card(start_date: str, end_date: str) -> dict:
    _today = datetime.now().date()
    if not start_date:
        start = _today - timedelta(days=30)
    else:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError("Invalid start_date format. Use YYYY-MM-DD")

    if not end_date:
        end = _today
    else:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError("Invalid end_date format. Use YYYY-MM-DD")

    if start > end:
        raise ValueError("Start date cannot be after end date")

    stock_card: List[Dict] = []
    total_purchase_weight = 0.0
    total_transport_weight = 0.0
    running_balance = 0.0

    current = start
    delta = timedelta(days=1)

    while current <= end:
        weight_date_str = current.strftime('%d.%m.%Y')

        grn_records = GRN.objects.filter(
            first_date=weight_date_str,
            is_deleted=False
        ).exclude(net_weight__in=['', '0', '0.0', None])

        grn_nos = [r.grn_no for r in grn_records if r.grn_no and r.grn_no != '-']
        grn_no_display = ', '.join(grn_nos) if grn_nos else '-'

        purchase_weight = sum(
            float(r.net_weight or 0) for r in grn_records
        )

        agg_records = DailyScrapMoveAggregate.objects.filter(
            weight_date=weight_date_str,
            is_deleted=False
        ).exclude(daily_net_weight__in=['', '0', '0.0', None])

        transport_weight = sum(
            float(r.daily_net_weight or 0) for r in agg_records
        )

        if purchase_weight == 0 and transport_weight == 0:
            current += delta
            continue

        daily_balance = purchase_weight - transport_weight
        running_balance += daily_balance

        total_purchase_weight += purchase_weight
        total_transport_weight += transport_weight

        stock_card.append({
            "weight_date": weight_date_str,
            "GRN No": grn_no_display,
            "Issue Voucher NO": "-",
            "purchase_weight": round(purchase_weight, 2),
            "transport_weight": round(transport_weight, 2),
            "balance": round(daily_balance, 2)
        })

        current += delta

    summary = {
        "total_purchase_weight": round(total_purchase_weight, 2),
        "total_transport_weight": round(total_transport_weight, 2),
        "Balance": round(running_balance, 2)
    }

    return {
        "stock_card": stock_card,
        "summary": summary
    }

@api_view(['GET'])
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

