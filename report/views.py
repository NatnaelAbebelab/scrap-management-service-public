import logging
import string
from calendar import month_abbr

from django.db.models import Count, Sum, FloatField, F, When, Case, Avg
from django.db.models.functions import Cast, TruncDay, TruncWeek, TruncMonth, TruncYear, Round
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from helperFunctions.date_manipulation import *
from helperFunctions.formatter import *
from helperFunctions.material_type import *
from helperFunctions.pagination import *
from helperFunctions.roles import *
from helperFunctions.status import *
from helperFunctions.validations import *
from report.serializers import GRNPlainReportFilterSerializer, GRNPlainReportResponseSerializer, \
    GRNAggregateReportFilterSerializer, GRNAggregateResponseSerializer, GeneralMetricsResponseSerializer, \
    ScrapGradePercentageResponseSerializer, YearlyPurchaseReportResponseSerializer
from report.services import generate_grn_plain_report, generate_grn_aggregate_report_service, generate_general_metrics, \
    generate_scrap_grade_percentage, generate_yearly_purchase_report
from utils.exceptions import *
from utils.permissions import role_required

# Create your views here.
logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def plain_grn_report(request):
    try:
        filter_serializer = GRNPlainReportFilterSerializer(data=request.GET)
        filter_serializer.is_valid(raise_exception=True)

        queryset, totals = generate_grn_plain_report(
            filter_serializer.validated_data
        )

        response_serializer = GRNPlainReportResponseSerializer({
            "data": queryset,
            "totals": totals
        })

        return JsonResponse({
            "result": "success",
            "message": "Plain GRN report generated successfully",
            "content": response_serializer.data
        }, status=status.HTTP_200_OK)

    except ValidationError as e:
        logger.error("Validation error occurred while generating plain GRN report: %s", e)
        return JsonResponse({
            "result": "error",
            "message": "Validation error occurred while generating plain GRN report"
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while generating plain GRN report: %s", e)
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while generating plain GRN report",
            "content": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def aggregate_report(request):
    # Validate filters
    filter_serializer = GRNAggregateReportFilterSerializer(data=request.GET)
    filter_serializer.is_valid(raise_exception=True)

    try:
        data, totals = generate_grn_aggregate_report_service(
            filter_serializer.validated_data
        )

        response_serializer = GRNAggregateResponseSerializer({
            "data": data,
            "totals": totals
        })

        return JsonResponse({
            "result": "success",
            "message": "Aggregate report generated successfully",
            "content": response_serializer.data
        }, status=status.HTTP_200_OK)

    except ValidationError as e:
       logger.error("Validation error occurred while generating aggregate report: %s", e)
       return JsonResponse({
           "result": "error",
           "message": "Validation error occurred while generating aggregate report"
       }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
       logger.error("Error occurred while generating aggregate report: %s", e)

       return JsonResponse({
           "result": "error",
           "message": "Error occurred while generating aggregate report",
           "content": str(e)
       }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def general_metrics(request):
    try:
        data = generate_general_metrics()

        serializer = GeneralMetricsResponseSerializer(data)

        return JsonResponse({
            "result": "success",
            "message": "General metrics successfully fetched",
            "content": serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception("Error occurred while fetching general metrics")

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while generating general metrics"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scrap_grade_percentage(request):
    try:
        data = generate_scrap_grade_percentage()

        serializer = ScrapGradePercentageResponseSerializer(data)

        return JsonResponse({
            "result": "success",
            "message": "Scrap grades percentage completed",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception("Error fetching scrap grade percentage")

        return JsonResponse({
            "result": "error",
            "message": "Scrap grades percentage failed"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def yearly_purchase_report(request):
    try:
        data = generate_yearly_purchase_report()

        serializer = YearlyPurchaseReportResponseSerializer({
            "data": list(data.values())
        })

        return JsonResponse({
            "result": "success",
            "message": "Yearly purchase report generated successfully",
            "content": serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception("Error generating yearly purchase report")

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while generating yearly report"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

"""
======================> Internal Processes Report <======================
"""

def daily_internal_aggregate_report(queryset, by_tin=False, by_material_type=False, by_start_date=False, by_end_date=False, by_status=False, start_date="", end_date=""):
    # Aggregate data by first_date
    queryset = queryset.annotate(period=TruncDay("casted_weight_date"))
    
    agency_info = None
    material_type_info = None
    start_date_info = None
    end_date_info = None
    status_info = None
    
    tin = queryset.values_list("TIN", flat=True).distinct().first()
    material_type = queryset.values_list("material_type", flat=True).distinct().first()
    _status = queryset.values_list("status", flat=True).distinct().first()
    
    if by_tin and queryset.exists():
        agency = Agency.objects.filter(TIN=tin).first()
        agency_info = {
            "fname": string.capwords(agency.fname),
            "lname": string.capwords(agency.lname),
            "TIN": agency.TIN,
            "business_name": string.capwords(agency.business_name)
        }

    if by_material_type and queryset.exists():
        material_type_info = {
            "name": MaterialType.get_material_type(material_type)
        }
    
    if by_start_date:
        start_date_info = {
            "start_date": start_date
        }
    
    if by_end_date:
        end_date_info = {
            "end_date": end_date
        }
    
    if by_status and queryset.exists():
        status_info = {
            "status": Status.get_status(_status).name
        }

    report_data = queryset.values("period").annotate(
        total_quantity=Count("_id"), 
        total_net_weight=Round(Sum(Cast("daily_net_weight", FloatField())), 2), 
        total_net_price=Round(Sum(Cast("net_price", FloatField())), 2),
        record_count=Count("_id"),
        formatted_period=Func(
            F("period"),
            function="TO_CHAR",
            template="%(function)s(%(expressions)s, 'Mon DD, YYYY')",
            output_field=CharField()
        )
    ).order_by("period")
    
    # choose which fields to return
    return_fields = [
        "total_net_weight",
        "total_net_price",
        "period",
        "formatted_period",
        "record_count"
    ]
        
    return {"data": list(report_data.values(*return_fields)), "extra_info": {"agency_info": agency_info, "material_type": material_type_info, "start_date_info": start_date_info, "end_date_info": end_date_info, "status_info": status_info}}
def weekly_internal_aggregate_report(queryset, by_tin=False, by_material_type=False, by_start_date=False, by_end_date=False, by_status=False, start_date="", end_date=""):
    # Aggregate data by first_date
    queryset = queryset.annotate(period=TruncWeek("casted_weight_date"))
    
    agency_info = None
    material_type_info = None
    start_date_info = None
    end_date_info = None
    status_info = None
    
    tin = queryset.values_list("TIN", flat=True).distinct().first()
    material_type = queryset.values_list("material_type", flat=True).distinct().first()
    _status = queryset.values_list("status", flat=True).distinct().first()
    
    if by_tin and queryset.exists():
        agency = Agency.objects.filter(TIN=tin).first()
        agency_info = {
            "fname": string.capwords(agency.fname),
            "lname": string.capwords(agency.lname),
            "TIN": agency.TIN,
            "business_name": string.capwords(agency.business_name)
        }

    if by_material_type and queryset.exists():
        material_type_info = {
            "name": MaterialType.get_material_type(material_type)
        }
    
    if by_start_date:
        start_date_info = {
            "start_date": start_date
        }
    
    if by_end_date:
        end_date_info = {
            "end_date": end_date
        }
    
    if by_status and queryset.exists():
        status_info = {
            "status": Status.get_status(_status).name
        }
        
    report_data = queryset.values("period").annotate(
        total_quantity=Count("_id"), 
        total_net_weight=Round(Sum(Cast("daily_net_weight", FloatField())), 2), 
        total_net_price=Round(Sum(Cast("net_price", FloatField())), 2),
        record_count=Count("_id"),
        formatted_period=Func(
            F("period"),
            function="TO_CHAR",
            template="%(function)s(%(expressions)s, 'Mon DD, YYYY')",
            output_field=CharField()
        )
    ).order_by("period")
    
    # choose which fields to return
    return_fields = [
        "total_net_weight",
        "total_net_price",
        "period",
        "formatted_period",
        "record_count"
    ]
   
    return {"data": list(report_data.values(*return_fields)), "extra_info": {"agency_info": agency_info, "material_type": material_type_info, "start_date_info": start_date_info, "end_date_info": end_date_info, "status_info": status_info}}
def monthly_internal_aggregate_report(queryset, by_tin=False, by_material_type=False, by_start_date=False, by_end_date=False, by_status=False, start_date="", end_date=""):
    # Aggregate data by first_date
    queryset = queryset.annotate(period=TruncMonth("casted_weight_date"))
    
    agency_info = None
    material_type_info = None
    start_date_info = None
    end_date_info = None
    status_info = None
    
    tin = queryset.values_list("TIN", flat=True).distinct().first()
    material_type = queryset.values_list("material_type", flat=True).distinct().first()
    _status = queryset.values_list("status", flat=True).distinct().first()
    
    if by_tin and queryset.exists():
        agency = Agency.objects.filter(TIN=tin).first()
        agency_info = {
            "fname": string.capwords(agency.fname),
            "lname": string.capwords(agency.lname),
            "TIN": agency.TIN,
            "business_name": string.capwords(agency.business_name)
        }

    if by_material_type and queryset.exists():
        material_type_info = {
            "name": MaterialType.get_material_type(material_type)
        }
    
    if by_start_date:
        start_date_info = {
            "start_date": start_date
        }
    
    if by_end_date:
        end_date_info = {
            "end_date": end_date
        }
    
    if by_status and queryset.exists():
        status_info = {
            "status": Status.get_status(_status).name
        }
    
    report_data = queryset.values("period").annotate(
        total_quantity=Count("_id"), 
        total_net_weight=Round(Sum(Cast("daily_net_weight", FloatField())), 2), 
        total_net_price=Round(Sum(Cast("net_price", FloatField())), 2),
        record_count=Count("_id"),
        formatted_period=Func(
            F("period"),
            function="TO_CHAR",
            template="%(function)s(%(expressions)s, 'Mon YYYY')",
            output_field=CharField()
        )
    ).order_by("period")
    
    # choose which fields to return
    return_fields = [
        "total_net_weight",
        "total_net_price",
        "period",
        "formatted_period",
        "record_count"
    ]
        
    return {"data": list(report_data.values(*return_fields)), "extra_info": {"agency_info": agency_info, "material_type": material_type_info, "start_date_info": start_date_info, "end_date_info": end_date_info, "status_info": status_info}}
def yearly_internal_aggregate_report(queryset, by_tin=False, by_material_type=False, by_start_date=False, by_end_date=False, by_status=False, start_date="", end_date=""):
    # Aggregate data by first_date
    queryset = queryset.annotate(period=TruncYear("casted_weight_date"))
    
    agency_info = None
    material_type_info = None
    start_date_info = None
    end_date_info = None
    status_info = None
    
    tin = queryset.values_list("TIN", flat=True).distinct().first()
    material_type = queryset.values_list("material_type", flat=True).distinct().first()
    _status = queryset.values_list("status", flat=True).distinct().first()
    
    if by_tin and queryset.exists():
        agency = Agency.objects.filter(TIN=tin).first()
        agency_info = {
            "fname": string.capwords(agency.fname),
            "lname": string.capwords(agency.lname),
            "TIN": agency.TIN,
            "business_name": string.capwords(agency.business_name)
        }

    if by_material_type and queryset.exists():
        material_type_info = {
            "name": MaterialType.get_material_type(material_type)
        }
    
    if by_start_date:
        start_date_info = {
            "start_date": start_date
        }
    
    if by_end_date:
        end_date_info = {
            "end_date": end_date
        }
    
    if by_status and queryset.exists():
        status_info = {
            "status": Status.get_status(_status).name
        }
    
    report_data = queryset.values("period").annotate(
        total_quantity=Count("_id"), 
        total_net_weight=Round(Sum(Cast("daily_net_weight", FloatField())), 2), 
        total_net_price=Round(Sum(Cast("net_price", FloatField())), 2),
        record_count=Count("_id"),
        formatted_period=Func(
            F("period"),
            function="TO_CHAR",
            template="%(function)s(%(expressions)s, 'YYYY')",
            output_field=CharField()
        )
    ).order_by("period")
    
    # choose which fields to return
    return_fields = [
        "total_net_weight",
        "total_net_price",
        "period",
        "formatted_period",
        "record_count"
    ]
        
    return {"data": list(report_data.values(*return_fields)), "extra_info": {"agency_info": agency_info, "material_type": material_type_info, "start_date_info": start_date_info, "end_date_info": end_date_info, "status_info": status_info}}
@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def internal_process_report(request):
    if request.method == "POST":
        tin = request.POST.get("tin", "").strip()
        material_type = request.POST.get("material_type", "").strip().lower()
        plate_no = request.POST.get("plate_no", "").strip()
        start_date = request.POST.get("start_date", "").strip()
        end_date = request.POST.get("end_date", "").strip()
        _status = request.POST.get("status", "").strip().lower()
        period = request.POST.get("period", "daily").strip().lower()
        
        # get the role of logged user
        role = get_user_role(request.user)
        
        allowed_status = ["approved"] if role == "supervisor" else (Status.get_status_by_role(role) or [])
        if _status and _status not in allowed_status:
            return JsonResponse({"result": "error", "message": f"{_status} status is not {role} scope"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            by_tin = False
            by_material_type = False
            by_start_date = False
            by_end_date = False
            by_status = False
            
            # Base QuerySet
            daily_scrap_move = DailyScrapMoveAggregate.objects.all().order_by("-record_time")
            
            # apply filter cases
            
            # Filter by TIN (Check if tin exists in Agency model)
            if tin and clean_tin(tin):
                agency = Agency.objects.filter(TIN=tin).first()
                if agency:
                    by_tin = True
                    daily_scrap_move = daily_scrap_move.filter(TIN=tin)
            
            # Filter by material type
            if material_type and is_valid_material(material_type):
                daily_scrap_move = daily_scrap_move.filter(material_type__iexact=material_type)
                by_material_type = True
            
            daily_scrap_move = daily_scrap_move.annotate(
                casted_weight_date=ToFormalDate("weight_date")
            )
            if start_date:
                start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                daily_scrap_move = daily_scrap_move.filter(casted_weight_date__gte=start_date)
                by_start_date = True
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                daily_scrap_move = daily_scrap_move.filter(casted_weight_date__lte=end_date)
                by_end_date = True
            
            # Filter by status
            if _status:
                daily_scrap_move = daily_scrap_move.filter(status__iexact=_status)
                by_status = True
            else:
                daily_scrap_move = daily_scrap_move.filter(status__in=allowed_status)

            # aggregate periodically
            if period == "daily":
                daily_report = daily_internal_aggregate_report(daily_scrap_move, by_tin, by_material_type, by_start_date, by_end_date, by_status, start_date, end_date)
                return JsonResponse({"result": "success", "message": "Scrap move are filtered daily successfully", "data": daily_report}, status=status.HTTP_200_OK)
            if period == "weekly":
                weekly_report = weekly_internal_aggregate_report(daily_scrap_move, by_tin, by_material_type, by_start_date, by_end_date, by_status, start_date, end_date)
                return JsonResponse({"result": "success", "message": "Scrap move are filtered weekly successfully", "data": weekly_report}, status=status.HTTP_200_OK)
            if period == "monthly":
                monthly_report = monthly_internal_aggregate_report(daily_scrap_move, by_tin, by_material_type, by_start_date, by_end_date, by_status, start_date, end_date)
                return JsonResponse({"result": "success", "message": "Scrap move are filtered monthly successfully", "data": monthly_report}, status=status.HTTP_200_OK)
            if period == "yearly":
                yearly_report = yearly_internal_aggregate_report(daily_scrap_move, by_tin, by_material_type, by_start_date, by_end_date, by_status, start_date, end_date)
                return JsonResponse({"result": "success", "message": "Scrap move are filtered yearly successfully", "data": yearly_report}, status=status.HTTP_200_OK)
            daily_report = daily_internal_aggregate_report(daily_scrap_move, by_tin, by_material_type, by_status)
            return JsonResponse({"result": "success", "message": "Scrap move are filtered daily successfully", "data": daily_report}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error occurred while aggregating scrap move: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while aggregating records"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "weight_man", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def internal_general_metrics(request):
    if request.method == "GET":
        start_date, end_date = get_last_week()

        try:
            daily_scrap_moves = DailyScrapMoveAggregate.objects.all().order_by("record_time")
            
            daily_scrap_moves = daily_scrap_moves.annotate(
                casted_weight_date=ToFormalDate("weight_date")
            )
            if start_date:
                daily_scrap_moves = daily_scrap_moves.filter(casted_weight_date__gte=start_date)
            if end_date:
                daily_scrap_moves = daily_scrap_moves.filter(casted_weight_date__lte=end_date)

            weekly_scrap_move = daily_scrap_moves.count()
            total_agencies = Agency.objects.all().count()
            total_daily_scrap_moves = DailyScrapMoveAggregate.objects.all().count()
            total_approved_daily_scrap_moves = DailyScrapMoveAggregate.objects.filter(status=Status.APPROVED.status_value).count()
            total_paid_daily_scrap_moves = DailyScrapMoveAggregate.objects.filter(status=Status.PAID.status_value).aggregate(
                total_net_price=Sum(Cast("net_price", FloatField())), 
                record_count=Count("_id")
            )
            total_paid_daily_scrap_moves_count = total_paid_daily_scrap_moves.get("record_count", 0)
            total_paid_amount = Decimal(str(total_paid_daily_scrap_moves.get("total_net_price"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) or 0
            return JsonResponse({"result": "success", "message": "General metrics successfully fetched", 
                                "weekly_scrap_move": weekly_scrap_move, "total_agencies": total_agencies, "total_daily_scrap_moves": total_daily_scrap_moves, "total_approved_daily_scrap_moves": total_approved_daily_scrap_moves, "total_paid_daily_scrap_moves_count": total_paid_daily_scrap_moves_count, "total_paid_amount": total_paid_amount,
                                "weekly_scrap_move_text": format_large_number(weekly_scrap_move), "total_agencies_text": format_large_number(total_agencies), "total_daily_scrap_moves_text": format_large_number(total_daily_scrap_moves), "total_approved_daily_scrap_moves_text": format_large_number(total_approved_daily_scrap_moves),
                                "total_paid_daily_scrap_moves_count_text": format_large_number(total_paid_daily_scrap_moves_count), "total_paid_amount_text": format_large_number(total_paid_amount)}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error occurred while fetching general metrics: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while generating general metrics"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "weight_man", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def yearly_internal_scrap_move(request):
    if request.method == "GET":
        try:
            by_material_type = False
            now = timezone.now()
            start_date = (now - timedelta(days=365)).replace(day=1)
            end_date = now
            
            # base grouping keys
            grouping_keys = ["period"]
            if by_material_type:
                grouping_keys.append("material_type")
            
            # Base QuerySet
            daily_scrap_moves = DailyScrapMoveAggregate.objects.annotate(
                casted_weight_date=ToFormalDate("weight_date")
            ).order_by("record_time")
            
            daily_scrap_moves = daily_scrap_moves.filter(Q(casted_weight_date__range=(start_date, end_date)) & Q(material_type__iexact=MaterialType.SCRAP.value))

            monthly_net = monthly_internal_aggregate_report(daily_scrap_moves, by_material_type)
            formatted_result = {}

            for month_data in monthly_net.get("data"):
                month = month_data["period"].month
                year = month_data["period"].year
                month_name = month_abbr[month].lower()  # Convert to 'jan', 'feb', etc.
                
                total_net_price = Decimal(str(float(month_data["total_net_price"]))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) or 0
                total_net_weight = Decimal(str(float(month_data["total_net_weight"]))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) or 0
                
                # Store in dictionary
                formatted_result[month_name] = {
                    "month": month_name,
                    "year": year,
                    "total_net_price": round(total_net_price, 2),
                    "total_net_weight": round(total_net_weight, 2),
                    "format_total_net_price": format_large_number(round(total_net_price, 2)),
                    "format_net_weight": format_large_number(round(total_net_weight, 2))
                }
            return JsonResponse({"result": "success", "message": "Yearly internal scrap move by month", "data": formatted_result}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error occurred while generating yearly report: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while generating yearly report", "data": ""}, status=status.HTTP_400_BAD_REQUEST)