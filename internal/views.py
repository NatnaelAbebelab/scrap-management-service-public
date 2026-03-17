import logging
import sys

from django.http import JsonResponse, Http404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from helperFunctions.pagination import *
from helperFunctions.validations import *
from utils.exceptions import *
from utils.permissions import role_required
from .services import *

# Create your views here.
logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')
MAX_FLOAT = sys.float_info.max  # Largest finite float in Python

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "weight_man"])])
def upload_excel_file(request):
    excel_file = request.FILES.get("csv_file")

    if not excel_file:
        return JsonResponse({
            "result": "error",
            "message": "File not provided"
        }, status=status.HTTP_400_BAD_REQUEST)

    if not excel_file.name.endswith(".xlsx"):
        return JsonResponse(
            {"result": "error", "message": "Invalid file format"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        result = process_scrap_excel(excel_file, request.user)

        return JsonResponse({
            "result": "success",
            "message": "File uploaded successfully",
            "created_records": result["created_records"],
            "skipped_records": result["skipped_records"]
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while uploading file: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while uploading file"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_factory_scrap_records(request):
    """
    Fetch factory scrap records based on a user role
    """

    try:
        queryset, allowed_status = get_factory_scrap_records_service(request.user)

        paginated_records = scrap_move_pagination(request, queryset)

        return JsonResponse({
                "result": "success",
                "data": paginated_records.data,
                "status_list": allowed_status
            }, status=status.HTTP_200_OK)

    except ValueError as e:
        return JsonResponse({
                "result": "error",
                "message": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while fetching factory scrap records: %s", e)

        return JsonResponse({
                "result": "error",
                "message": "Error occurred while fetching factory scrap records"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def filter_factory_scrap_records(request):
    """
    Filter factory scrap records
    Filters:
    - tin
    - material_type
    - plate_no
    - start_date
    - end_date
    - status
    """

    serializer = FactoryScrapFilterSerializer(data=request.GET)

    if not serializer.is_valid():
        return JsonResponse({
            "result": "error",
            "message": "Invalid filter parameters",
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        queryset = filter_factory_scrap_records_service(
            serializer.validated_data
        )

        paginated_records = scrap_move_pagination(
            request,
            queryset
        )

        return JsonResponse({
            "result": "success",
            "message": "Factory scrap records filtered successfully",
            "content": paginated_records.data,
        }, status=status.HTTP_200_OK)

    except ValueError as e:

        return JsonResponse(
            {
                "result": "error",
                "message": str(e)
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:
        logger.error("Error occurred while filtering factory scrap records: %s", e)

        return JsonResponse(
            {
                "result": "error",
                "message": "Internal server error"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def add_agency(request):
    """
    Register a new agency
    """
    try:
        serializer = AgencyCreateSerializer(data=request.POST)

        if not serializer.is_valid():
            return JsonResponse(
                {
                    "result": "error",
                    "errors": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        new_agency = create_agency(
            serializer.validated_data,
            request.user,
            today
        )

        serialized_result = AgencySerializer(new_agency).data

        return JsonResponse(
            {
                "result": "success",
                "message": "Agency registered successfully",
                "content": serialized_result
            },
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error("Error occurred while registering agency: %s", e)

        return JsonResponse(
            {
                "result": "error",
                "message": "Internal server error"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "finance", "manager"])])
def get_agencies(request):
    try:
        queryset = get_agencies_service()

        paginated_records = agency_pagination(request, queryset)

        return JsonResponse(
            {
                "result": "success",
                "message": "Agencies fetched successfully",
                "data": paginated_records.data,
            }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while fetching agencies: %s", e)

        return JsonResponse(
            {
                "result": "error",
                "message": "Internal server error"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def update_agency(request):
    try:

        serializer = AgencyUpdateSerializer(data=request.data) # request.data => request body

        if not serializer.is_valid():
            return JsonResponse({
                "result": "error",
                "message": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        changed_agency = update_agency_service(
            serializer.validated_data,
            request.user
        )

        serialized_result = AgencySerializer(changed_agency).data

        return JsonResponse({
            "result": "success",
            "message": "Agency updated successfully",
            "content": serialized_result
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while updating agency: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Internal server error"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def delete_agency(request, agency_id):
    try:
        delete_agency_service(
            agency_id,
            request.user
        )

        return JsonResponse({
            "result": "success",
            "message": "Agency deleted successfully",
        }, status=status.HTTP_204_NO_CONTENT) # 204 No Content is used when the action is successful but there is no content to return

    except Http404:
        return JsonResponse({
            "result": "error",
            "message": "Agency not found"
        }, status=status.HTTP_404_NOT_FOUND)

    except ValueError:
        return JsonResponse({
            "result": "error",
            "message": "Agency ID is not valid ID"
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while deleting agency: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Internal server error"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def restore_agency(request, tin):
    try:
        restored_agency = restore_agency_service(
            tin,
            request.user
        )

        serialized_result = AgencySerializer(restored_agency).data

        return JsonResponse({
            "result": "success",
            "message": f"Agency ({restored_agency.TIN}) restored successfully",
            "content": serialized_result
        }, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({
            "result": "error",
            "message": "Record not found"
        }, status=status.HTTP_404_NOT_FOUND)

    except ValueError:
        return JsonResponse({
            "result": "error",
            "message": "Agency ID is not valid ID"
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while restoring agency: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Internal server error"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def add_agreement(request):
    try:
        serializer = AgreementCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return JsonResponse({
                "result": "error",
                "message": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        agreement = add_agreement_service(
            serializer.validated_data,
            request.user
        )

        serialized_result = AgreementSerializer(agreement).data

        return JsonResponse({
            "result": "success",
            "message": "Agreement submitted successfully",
            "content": serialized_result
        }, status=status.HTTP_201_CREATED)

    except ValueError as e:
        return JsonResponse({
            "result": "error",
            "message": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while adding agreement: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Internal server error"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "finance", "manager"])])
def get_agreements(request):
    try:
        agreements = Agreement.objects.all().order_by("-record_time")

        paginated_records = agreement_pagination(request, agreements)

        return JsonResponse({
            "result": "success",
            "message": "Agreements fetched successfully",
            "content": paginated_records.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while fetching agreements: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Internal server error"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def update_agreement(request):
    try:
        serializer = AgreementUpdateSerializer(data=request.data)

        if not serializer.is_valid():

            return JsonResponse({
                "result": "error",
                "message": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        updated_agreement = update_agreement_service(
            serializer.validated_data,
            request.user
        )

        serialized_result = AgreementSerializer(updated_agreement).data

        return JsonResponse({
            "result": "success",
            "message": "Agreement updated successfully",
            "content": serialized_result
        }, status=status.HTTP_200_OK)

    except ValueError as e:
        return JsonResponse({
            "result": "error",
            "message": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while updating agreement: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while updating agreement:" + str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def update_agreement_range(request):
    try:
        serializer = AgreementRangeUpdateSerializer(data=request.data)

        if not serializer.is_valid():
            return JsonResponse({
                "result": "error",
                "message": "Validation error",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        updated_agreement_range = update_agreement_ranges(
            validated_data=serializer.validated_data,
            user=request.user
        )

        serialized_result = AgreementRangeSerializer(updated_agreement_range).data

        return JsonResponse({
            "result": "success",
            "message": "Agreement ranges updated successfully",
            "content": serialized_result
        }, status=status.HTTP_200_OK)

    except ValueError as e:
        return JsonResponse({
            "result": "error",
            "message": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error updating agreement ranges: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "An unexpected error occurred"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def delete_agreement(request, agreement_id):
    try:
        delete_agreement_service(
            agreement_id=agreement_id
        )

        return JsonResponse({
            "result": "success",
            "message": "Agreement deleted successfully"
        }, status=status.HTTP_204_NO_CONTENT)

    except ValueError:
        return JsonResponse({
            "result": "error",
            "message": "Invalid agreement ID"
        }, status=status.HTTP_400_BAD_REQUEST)

    except Http404:
        return JsonResponse({
            "result": "error",
            "message": "Agreement not found"
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error("Delete operation failed: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Delete operation failed"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_daily_scrap_move_aggregate(request):
    """
    Fetch daily aggregated scrap move
    """
    try:
        serializer = DailyScrapMoveFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        queryset = filter_daily_scrap_move_aggregate(
            serializer.validated_data
        )

        paginated_records = daily_scrap_move_pagination(request, queryset)

        return JsonResponse({
            "result": "success",
            "message": "Daily scrap move aggregate fetched successfully",
            "content": paginated_records.data
        }, status=status.HTTP_200_OK)

    except ValidationError as e:
        return JsonResponse({
            "result": "error",
            "message": e.detail
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while fetching daily scrap move aggregate: %s",e)

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while fetching daily scrap move aggregate"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def get_daily_performance_calculation(request):
    """
    Calculate daily performance metrics
    """
    try:
        serializer = DailyPerformanceFilterSerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)

        queryset = calculate_daily_performance(serializer.validated_data)

        return JsonResponse({
            "result": "success",
            "message": "Daily performance calculation result",
            "content": list(queryset)
        }, status=status.HTTP_200_OK)

    except ValidationError as e:
        return JsonResponse({
            "result": "error",
            "message": e.detail
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while calculating daily performance: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while calculating daily performance"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def approve_record_supervisor(request):
    """
    Supervisor approves daily scrap move records
    """
    try:
        serializer = ApproveDailyScrapMoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        valid_ids = serializer.validated_data["data"]

        updated_count = approve_daily_scrap_move_records(valid_ids)

        return JsonResponse({
            "result": "success",
            "message": f"{updated_count} daily scrap mov't records approved",
            "content": updated_count
        }, status=status.HTTP_200_OK)

    except ValidationError as e:
        return JsonResponse({
            "result": "error",
            "message": e.detail
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while approving daily scrap mov\'t: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while approving daily scrap mov't"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "factory_manager"])])
def approve_record_factory_manager(request):
    """
    Factory manager approves daily scrap move records
    """
    try:
        serializer = ApproveFactoryManagerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        valid_ids = serializer.validated_data["data"]

        updated_count = approve_factory_manager_records(valid_ids)

        return JsonResponse({
            "result": "success",
            "message": f"{updated_count} daily scrap mov't records approved by factory manager",
            "content": updated_count,
        }, status=status.HTTP_200_OK)

    except ValidationError as e:
        return JsonResponse({
            "result": "error",
            "message": e.detail
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("Error occurred while approving daily scrap mov\'t: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Error occurred while approving daily scrap mov't"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "finance"])])
def pay_agency_finance(request):
    """
    Pay agency:
    update paid_amount and remaining_amount
    """
    try:
        serializer = PayAgencyFinanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        valid_ids = serializer.validated_data["data"]

        result = pay_agency_finance_service(valid_ids)

        return JsonResponse({
            "result": "success",
            "message": "Payment is successful",
            "content": result
        }, status=status.HTTP_200_OK)

    except ValidationError as e:
        return JsonResponse({
            "result": "error",
            "message": e.detail
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(
            "Error occurred while processing agency payment: %s", e
        )
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while processing agency payment"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)