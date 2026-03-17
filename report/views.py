import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from helperFunctions.date_manipulation import *
from helperFunctions.formatter import *
from helperFunctions.pagination import *
from helperFunctions.validations import *
from report.serializers import GRNPlainReportFilterSerializer, GRNPlainReportResponseSerializer, \
    GRNAggregateReportFilterSerializer, GRNAggregateResponseSerializer, GeneralMetricsResponseSerializer, \
    ScrapGradePercentageResponseSerializer, YearlyPurchaseReportResponseSerializer, InternalProcessReportSerializer
from report.services import generate_grn_plain_report, generate_grn_aggregate_report_service, generate_general_metrics, \
    generate_scrap_grade_percentage, generate_yearly_purchase_report, internal_process_report_service, \
    internal_general_metrics_service, yearly_internal_scrap_move_service
from utils.exceptions import *

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
        logger.error("Error occurred while generating general metrics: %s", e)

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
        logger.error("Error occurred while scrap grades percentage: %s", e)

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
        logger.error("Error occurred while generating yearly purchase report: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while generating yearly report"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

"""
======================> Internal Processes Report <======================
"""
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def internal_process_report(request):
    """
    Internal process aggregated report
    """
    try:
        serializer = InternalProcessReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = internal_process_report_service(
            serializer.validated_data
        )

        return JsonResponse({
            "result": "success",
            "message": f"Scrap move filtered {serializer.validated_data.get('period')} successfully",
            "content": result
        }, status=status.HTTP_200_OK)

    except serializers.ValidationError as e:
        return JsonResponse({
            "result": "error",
            "message": e.detail
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while aggregating scrap move: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while aggregating records"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def internal_general_metrics(request):
    """
    API endpoint for internal general metrics
    """
    try:
        start_date, end_date = get_last_week()

        result = internal_general_metrics_service(
            start_date=start_date,
            end_date=end_date
        )

        # Add formatted values (presentation layer)
        response_data = {
            "result": "success",
            "message": "General metrics successfully fetched",

            **result,

            "weekly_scrap_move_text": format_large_number(result["weekly_scrap_move"]),
            "total_agencies_text": format_large_number(result["total_agencies"]),
            "total_daily_scrap_moves_text": format_large_number(result["total_daily_scrap_moves"]),
            "total_approved_daily_scrap_moves_text": format_large_number(result["total_approved_daily_scrap_moves"]),
            "total_paid_daily_scrap_moves_count_text": format_large_number(result["total_paid_daily_scrap_moves_count"]),
            "total_paid_amount_text": format_large_number(result["total_paid_amount"]),
        }

        return JsonResponse(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while fetching general metrics: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while generating general metrics"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def yearly_internal_scrap_move(request):
    """
    API endpoint for yearly internal scrap move (monthly breakdown)
    """
    try:
        data = yearly_internal_scrap_move_service()

        return JsonResponse({
            "result": "success",
            "message": "Yearly internal scrap move by month",
            "data": data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while generating yearly report: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while generating yearly report",
            "data": {}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)