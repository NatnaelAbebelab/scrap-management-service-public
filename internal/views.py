import logging
import sys

from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Count, Sum, FloatField
from django.db.models.expressions import F
from django.db.models.functions import Cast, Round
from django.http import JsonResponse, Http404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from helperFunctions.material_type import *
from helperFunctions.pagination import *
from helperFunctions.roles import *
from helperFunctions.status import *
from helperFunctions.validations import *
from utils.exceptions import *
from utils.permissions import role_required
from .services import *

# Create your views here.
logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')
MAX_FLOAT = sys.float_info.max  # Largest finite float in Python

def filter_daily_scrap_move_aggregate(role, tin, material_type, start_date, end_date, status):
    """
    Get daily scrap move aggregate based on the filters
    """
    allowed_status = Status.get_status_by_role(role)
    if status and status not in allowed_status:
        raise StatusException(f"{status} is not belong to {role}")
    try:
        # Base QuerySet
        daily_scrap_move = DailyScrapMoveAggregate.objects.all().order_by("-record_time")
        
        # apply filter cases
        
        # Filter by TIN (Check if tin exists in Agency model)
        if tin and clean_tin(tin):
            agency = Agency.objects.filter(TIN=tin).first()
            if agency:
                daily_scrap_move = daily_scrap_move.filter(TIN=tin)
        
        # Filter by material type
        if material_type and is_valid_material(material_type):
            daily_scrap_move = daily_scrap_move.filter(material_type__iexact=material_type)

        daily_scrap_move = daily_scrap_move.annotate(
            casted_weight_date=ToFormalDate("weight_date")
        )
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            daily_scrap_move = daily_scrap_move.filter(casted_weight_date__gte=start_date)
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            daily_scrap_move = daily_scrap_move.filter(casted_weight_date__lte=end_date)

        # Filter by status
        if status:
            daily_scrap_move = daily_scrap_move.filter(status=status)
        else:
            daily_scrap_move = daily_scrap_move.filter(status__in=allowed_status)
        
        return daily_scrap_move.all()
    
    except Exception as e:
        logger.error("Error occurred while filtering daily move aggregate: %s", e)
        return FilterException("Error occurred while filtering daily move aggregate")
def daily_performance_calculator(tin, plate_no, start_date, end_date):
    """
    Calculates driver performance within a given weight date range.
    Returns total first weight, second weight, net weight, and record count.
    """

    # Annotate first_date conversion supporting both formats
    queryset = FactoryScrapMove.objects.annotate(
        first_date_as_date=ToDateTime(F("first_date"))  # Convert first_date to DateField
    )

    # Apply filters conditionally
    filters = Q()

    if tin and clean_tin(tin):
        filters &= Q(agency=tin)  # TIN is stored in the "agency" field

    if plate_no:
        filters &= Q(plate_no__iexact=plate_no)
    if start_date:
        # Ensure start_date is in the correct format (YYYY-MM-DD) for comparison
        start_date_obj = datetime.strptime(start_date, "%d.%m.%Y") if "." in start_date else datetime.strptime(start_date, "%Y-%m-%d")
        filters &= Q(first_date_as_date__gte=start_date_obj.date())  # Convert to date object for comparison

    if end_date:
        # Ensure end_date is in the correct format (YYYY-MM-DD) for comparison
        end_date_obj = datetime.strptime(end_date, "%d.%m.%Y") if "." in end_date else datetime.strptime(end_date, "%Y-%m-%d")
        filters &= Q(first_date_as_date__lte=end_date_obj.date())  # Convert to date object for comparison

    # Apply filters to queryset
    queryset = queryset.filter(filters)

    # Perform aggregation
    aggregated_data = (
        queryset
        .values("plate_no", "first_date")
        .annotate(
            total_first_weight=Round(Sum(Cast("first_weight", FloatField())), 2),
            total_second_weight=Round(Sum(Cast("second_weight", FloatField())), 2),
            total_net_weight=Round(Sum(Cast("net_weight", FloatField())), 2),
            total_records=Count("_id"),
            driver_names=ArrayAgg("driver_name", distinct=True),
        )
        .order_by("plate_no", "first_date")
    )

    return {"daily_performance_calculation": list(aggregated_data)}

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
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "factory_manager", "finance", "manager"])])
def get_daily_scrap_move_aggregate(request):
    """
    Fetch daily aggregated scrap move
    """
    try :
        role = get_user_role(request.user)
        get_daily_scrap_move = filter_daily_scrap_move_aggregate(role, "", "", "", "", "")
        paginated_records = daily_scrap_move_pagination(request, get_daily_scrap_move)
        return JsonResponse({
            "result": "success",
            "data": paginated_records.data,
        }, status=status.HTTP_200_OK)
    except StatusException as e:
        return JsonResponse({"result": "error", "message": e.message}, status=status.HTTP_400_BAD_REQUEST)
    except FilterException as e:
        return JsonResponse({"result": "error", "message": e.message}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Error occurred while fetching daily scrap move aggregate: %s", e)
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while fetching daily scrap move aggregate",
        }, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "factory_manager", "finance", "manager"])])
def get_filtered_scrap_move_aggregate(request):
    """
    Filter Daily scrap move records based on some filter criteria ==> TIN, Material Type, Start Date, End Date, Status
    """
    tin = request.query_params.get("tin", "").strip()
    material_type = request.query_params.get("material_type", "").strip().lower()
    start_date = request.query_params.get("start_date", "").strip()
    end_date = request.query_params.get("end_date", "").strip()
    _status = request.query_params.get("status", "").strip().lower()
    
    try:
        # get the role of the user
        role = get_user_role(request.user)
        get_daily_scrap_move = filter_daily_scrap_move_aggregate(role, tin, material_type, start_date, end_date, _status)
        paginated_query = filter_daily_scrap_move_pagination(request, get_daily_scrap_move, start_date, end_date)
        status_list = Status.get_status_by_role(role)
        return JsonResponse({"result": "success", "message": "Daily scrap moves are filtered successfully", "data": paginated_query.data, "status_list": status_list}, status=status.HTTP_200_OK)
    except ValueError:
        return JsonResponse({"result": "error", "message": f"TIN {tin} is invalid"}, status=status.HTTP_400_BAD_REQUEST)
    except StatusException as e:
        return JsonResponse({"result": "error", "message": e.message}, status=status.HTTP_400_BAD_REQUEST)
    except FilterException as e:
        return JsonResponse({"result": "error", "message": e.message}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Error occurred while filtering daily scrap move %s:", e)
        return JsonResponse({"result": "error", "message": "Error occurred while filtering daily scrap move"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def get_daily_performance_calculation(request):
    """
    Calculate daily performance metrics for a given TIN and plate number
    """
    if request.method == "GET":
        tin = request.GET.get("tin", "").strip()
        plate_no = request.GET.get("plate_no", "").strip()
        start_date = request.GET.get("start_date", "").strip()
        end_date = request.GET.get("end_date", "").strip()
        try:
            result = daily_performance_calculator(tin, plate_no, start_date, end_date)
            return JsonResponse({"result": "success", "message": "Daily performance calculation result", "data": result}, status=status.HTTP_200_OK)
        except ValueError:
            return JsonResponse({"result": "error", "message": f"TIN {tin} is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Error occurred while calculating daily performance: %s", e)
            return JsonResponse({"result" : "error", "message" : "Error occurred while calculating daily performance"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def approve_record_supervisor(request):
    if request.method == "PATCH":
        _id_collections = request.POST.getlist("data")

        if not _id_collections:
            return JsonResponse({"result": "error", "message": "There is no data on the request"}, status=status.HTTP_400_BAD_REQUEST)
        valid_ids = [uuid for uuid in _id_collections if is_valid_uuid(uuid)]
        try:
            DailyScrapMoveAggregate.objects.filter(_id__in=valid_ids).exclude(status="approved_manager").update(status="approved", updated_at=today, record_time=timezone.now())
            return JsonResponse({"result": "success", "message": "Daily scrap mov't records approved"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error occurred while approving daily scrap mov\'t: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while approving daily scrap mov\'t"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "factory_manager"])])
def approve_record_factory_manager(request):
    if request.method == "PATCH":
        _id_collections = request.POST.getlist("data")

        if not _id_collections:
            return JsonResponse({"result": "error", "message": "There is no data on the request"}, status=status.HTTP_400_BAD_REQUEST)
        valid_ids = [uuid for uuid in _id_collections if is_valid_uuid(uuid)]
        try:
            DailyScrapMoveAggregate.objects.filter(_id__in=valid_ids).update(status="approved_manager", updated_at=today, record_time=timezone.now())
            return JsonResponse({"result": "success", "message": "Daily scrap mov't records approved"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error occurred while approving daily scrap mov\'t: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while approving daily scrap mov\'t"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "finance"])])
def pay_agency_finance(request):
    """
    Pay agency ===> update the agency remaining amount and paid amount
    """
    if request.method == "PATCH":
        _id_collections = request.POST.getlist("data")
        
        if not _id_collections:
            return JsonResponse({"result": "error", "message": "There is no data on the request"}, status=status.HTTP_400_BAD_REQUEST) 
        valid_ids = [uuid for uuid in _id_collections if is_valid_uuid(uuid)]
        try:
            # Get affected TINs and total paid amount per TIN
            affected_agencies = (
                DailyScrapMoveAggregate.objects
                .filter(_id__in=valid_ids)
                .values("TIN")  # Group by TIN
                .annotate(total_paid=Sum(Cast("net_price", FloatField())))  # Sum the net_price for each TIN
            )
            DailyScrapMoveAggregate.objects.filter(_id__in=valid_ids).update(status="paid", updated_at=today, record_time=timezone.now())
            
            # get TIN and net price each then + on paid amount and - on remaining amount
            # Update Agency model for each affected TIN
            for agency_data in affected_agencies:
                tin = agency_data["TIN"]
                paid_amount = agency_data["total_paid"]

                Agency.objects.filter(TIN=tin).update(
                    paid_amount=Round(Cast(F("paid_amount"), FloatField()) + float(paid_amount), 2),
                    remaining_amount=Round(Cast(F("remaining_amount"), FloatField()) - float(paid_amount), 2),
                    updated_at=today, record_time=timezone.now()
                )
            return JsonResponse({"result": "success", "message": "Payment is successful"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error occurred while approving daily scrap mov\'t: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while approving daily scrap mov\'t"}, status=status.HTTP_400_BAD_REQUEST)