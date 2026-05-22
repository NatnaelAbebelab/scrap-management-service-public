import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import permission_classes, api_view
from rest_framework.permissions import IsAuthenticated

from helperFunctions.pagination import material_requisition_pagination, raw_material_issue_pagination, \
    melting_plants_pagination
from material.enums import RequisitionStatus, IssueStatus
from material.models import MaterialRequisition, RawMaterialIssue, MeltingPlants
from material.serializers import MaterialRequisitionSerializer, RawMaterialIssueSerializer, \
    ApprovedMaterialRequisitionSerializer, MeltingPlantsSerializer, MeltingPlantCreateSerializer, \
    MeltingPlantUpdateSerializer, MaterialRequisitionCreateSerializer, MaterialRequisitionFilterSerializer, \
    MaterialRequisitionEditSerializer, RawMaterialIssueCreateSerializer, RawMaterialIssueFilterSerializer, \
    RawMaterialIssueEditSerializer, MaterialRequisitionReportSerializer, RawMaterialIssueReportSerializer
from material.services import create_melting_plant, update_melting_plant, create_material_requisition, \
    get_filtered_material_requisitions, update_material_requisition, create_raw_material_issue_service, \
    get_raw_material_issues_service, edit_raw_material_issue_service, change_raw_material_issue_status_service, \
    filter_material_requisition_service, filter_raw_material_issue_service
from utils.permissions import role_required

# Create your views here.
logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')

def assign_if_not_empty(instance, field, value):
    if value not in [None, ""]:
        setattr(instance, field, value)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_melting_plants(request):
    try:
        melting_plants = MeltingPlants.objects.all().order_by('-record_time')

        serialized_melting_plants = melting_plants_pagination(request, melting_plants)

        return JsonResponse({
            "result": "success",
            "message": "fetched successfully",
            "content": serialized_melting_plants.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error occurred while fetching melting plants: {e}")

        return JsonResponse({
            "result": "error",
            "data": e
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def add_melting_plant(request):
    """
    Create Melting Plant
    """

    serializer = MeltingPlantCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        melting_plant = create_melting_plant(
            serializer.validated_data,
            request.user
        )

        response_serializer = MeltingPlantsSerializer(melting_plant)

        return JsonResponse(
            {
                "result": "success",
                "message": "Melting plant created successfully",
                "content": response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error(f"Error creating melting plant: {e}")
        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while creating melting plant",
                "content": str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['PUT'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def edit_melting_plant(request):
    """
    Edit existing melting plant

    Expected request.data:
    {
        "_id": "uuid",
        "new_name": "NEW_PLANT"
    }
    """

    serializer = MeltingPlantUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        melting_plant = update_melting_plant(
            serializer.validated_data["_id"],
            serializer.validated_data,
            request.user
        )

        if not melting_plant:
            return JsonResponse(
                {
                    "result": "error",
                    "message": "Melting plant not found",
                    "content": ""
                }, status=status.HTTP_404_NOT_FOUND
            )

        response_serializer = MeltingPlantsSerializer(melting_plant)

        return JsonResponse(
            {
                "result": "success",
                "message": "Melting plant updated successfully",
                "content": response_serializer.data
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error updating melting plant: {e}")
        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while updating melting plant",
                "content": str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def delete_melting_plant(request, melting_plant_id):
    try:
        melting_plant_id = get_object_or_404(MeltingPlants.objects, _id=melting_plant_id)
        melting_plant_id.delete()

        return JsonResponse({
            "result": "success",
            "message": "Melting plant is deleted successfully",
            "content": ""
        }, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({
            "result": "error",
            "message": "Melting plant is not found"
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Error deleting melting plant: {e}")
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while deleting melting plant",
            "content": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_material_requisitions(request):
    serializer = MaterialRequisitionFilterSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    filters = serializer.validated_data

    try:
        requisitions = get_filtered_material_requisitions(filters)
        serialized = material_requisition_pagination(request, requisitions)

        return JsonResponse({
            "result": "success",
            "message": "Fetched successfully",
            "content": serialized.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error fetching material requisitions: {e}")

        return JsonResponse(
            {
                "result": "error",
                "message": "Error fetching requisitions",
                "content": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_material_requisition(request, requisition_id):
    try:
        requisition = get_object_or_404(MaterialRequisition, _id=requisition_id, is_deleted=False)
        serializer = MaterialRequisitionSerializer(requisition)

        return JsonResponse({
            "result": "success",
            "message": "fetched successfully",
            "content": serializer.data
        }, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({
            "result": "error",
            "message": "Resource not found"
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Error fetching material requisition: {e}")

        return JsonResponse(
            {
                "result": "error",
                "message": "An error occurred",
                "content": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_approved_material_requisitions(request):
    approved_requisitions = MaterialRequisition.objects.filter(
        requisition_status__in=[RequisitionStatus.APPROVED.value, RequisitionStatus.PARTIALLY_RECEIVED.value]
    ).order_by('-record_time')

    serializer = ApprovedMaterialRequisitionSerializer(approved_requisitions, many=True)

    return JsonResponse({
        "result": "success",
        "message": "Approved material requisitions loaded successfully",
        "content": serializer.data
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "forman"])])
def add_material_requisition(request):
    """
    Add a new material requisition
    """

    serializer = MaterialRequisitionCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        requisition = create_material_requisition(serializer.validated_data, request.user)

        response_serializer = MaterialRequisitionSerializer(requisition)

        return JsonResponse(
            {
                "result": "success",
                "message": "Material requisition created successfully",
                "content": response_serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    except ValueError as ve:
        logger.error(f"Error creating material requisition: {ve}")
        return JsonResponse(
            {
                "result": "error",
                "message": str(ve),
                "content": ""
            }, status=status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:
        logger.error(f"Error creating material requisition: {e}")
        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while creating requisition",
                "content": str(e)
            }, status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['PUT'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "forman"])])
def edit_material_requisition(request):
    """
    Expected request.data format:
    {
        "_id": "<requisition_uuid>",
        "plant": "<melting_plant_uuid>",
        "requisition_date": "YYYY-MM-DD",
        "requisition_no": "REQ-001",
        "items": [
            {"_id": "<item_uuid>", "item_code": "IT001", "item_name": "Item 1", "quantity": 5, "unit_price": 10.5},
            {"item_code": "IT002", "item_name": "Item 2", "quantity": 2, "unit_price": 20.0}
        ]
    }

    Only non-null and non-blank fields are updated.
    Items can be updated, created, or deleted.
    """
    serializer = MaterialRequisitionEditSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    validated_data = serializer.validated_data

    try:
        requisition = update_material_requisition(request.user, validated_data)
        serialized = MaterialRequisitionSerializer(requisition)

        return JsonResponse(
            {
                "result": "success",
                "message": "Material requisition updated successfully",
                "content": serialized.data
            },
            status=status.HTTP_200_OK
        )

    except Http404 as e:
        return JsonResponse(
            {
                "result": "error",
                "message": "Resource not found",
                "content": str(e)
            },
            status=status.HTTP_404_NOT_FOUND
        )

    except Exception as e:
        logger.error(f"Error updating material requisition: {e}")

        return JsonResponse(
            {
                "result": "error",
                "message": str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "department_head"])])
def approve_material_requisition(request, requisition_id):
    try:
        requisition = MaterialRequisition.objects.get(_id=requisition_id)
        requisition.requisition_status = RequisitionStatus.APPROVED.value
        requisition.approved_by = request.user
        requisition.approved_at = timezone.now()
        requisition.updated_by = request.user
        requisition.save()

        serialized_requisition = MaterialRequisitionSerializer(requisition)

        return JsonResponse({
            "result": "success",
            "message": "Material requisition approved successfully",
            "content": serialized_requisition.data
        }, status=status.HTTP_200_OK)

    except MaterialRequisition.DoesNotExist:
        return JsonResponse({
            "result": "error",
            "message": "Material requisition not found"
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Error approving material requisition: {e}")

        return JsonResponse({
            "result": "error",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "department_head"])])
@transaction.atomic
def delete_material_requisition(request, requisition_id):
    try:
        requisition = get_object_or_404(MaterialRequisition.objects, _id=requisition_id)

        issues = RawMaterialIssue.objects.filter(
            material_requisition=requisition
        ).all()

        if issues.exists():
            return JsonResponse({
                "result": "error",
                "message": "There are material issues associated with this requisition. Please delete the issues first.",
                "issues_count": issues.count()
            }, status=status.HTTP_400_BAD_REQUEST)

        requisition.delete()

        return JsonResponse({
            "result": "success",
            "message": "Material requisition is deleted successfully",
            "content": ""
        }, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({
            "result": "error",
            "message": "Material requisition not found"
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Error deleting material requisition: {e}")

        return JsonResponse({
            "result": "error",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_raw_material_issues(request):
    try:
        serializer = RawMaterialIssueFilterSerializer(data=request.query_params)

        if not serializer.is_valid():
            return JsonResponse({
                "result": "error",
                "message": "Validation error",
                "content": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        issues = get_raw_material_issues_service(
            serializer.validated_data
        )

        paginated = raw_material_issue_pagination(request, issues)

        return JsonResponse({
            "result": "success",
            "message": "Fetched successfully",
            "content": paginated.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error occurred while fetching issues: {e}")
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while fetching issues",
            "content": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_raw_material_issue(request, issue_id):
    try:
        issue = get_object_or_404(RawMaterialIssue, _id=issue_id, is_deleted=False)
        serializer = RawMaterialIssueSerializer(issue)

        return JsonResponse({
            "result": "success",
            "message": "Raw material issue loaded successfully",
            "content": serializer.data
        }, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({
            "result": "error",
            "message": "Resource not found"
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Error occurred while fetching issue: {e}")
        return JsonResponse({
            "result": "error",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "store_keeper", 'purchaser'])])
def add_raw_material_issue(request):

    serializer = RawMaterialIssueCreateSerializer(data=request.data)

    if not serializer.is_valid():
        return JsonResponse({
            "result": "error",
            "message": "Validation error",
            "content": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        issue = create_raw_material_issue_service(
            serializer.validated_data,
            request.user
        )

        serialized_issue = RawMaterialIssueSerializer(issue)

        return JsonResponse({
            "result": "success",
            "message": "Raw material issue created successfully",
            "content": serialized_issue.data
        }, status=status.HTTP_201_CREATED)

    except ValueError as e:
        return JsonResponse({
            "result": "error",
            "message": str(e),
            "content": ""
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error occurred while creating material issue: {e}")
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while creating material issue",
            "content": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "store_keeper", 'purchaser', 'supervisor'])])
def edit_raw_material_issue(request):
    serializer = RawMaterialIssueEditSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse({
            "result": "error",
            "message": "Validation error",
            "content": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        issue = edit_raw_material_issue_service(serializer.validated_data, request.user)
        serialized_issue = RawMaterialIssueSerializer(issue)

        return JsonResponse({
            "result": "success",
            "message": "Raw Material issue updated successfully",
            "content": serialized_issue.data
        }, status=status.HTTP_200_OK)

    except ValueError as e:
        return JsonResponse({
            "result": "error",
            "message": str(e),
            "content": ""
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error occurred while editing issue: {e}")
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while editing issue",
            "content": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", 'supervisor'])])
def change_raw_material_issue_status(request, issue_id):
    """
    Endpoint to change RawMaterialIssue status:
        NEW -> ISSUED -> APPROVED (updates stock balance)
    """
    if not issue_id:
        return JsonResponse({
            "result": "error",
            "message": "Issue ID is required",
            "content": ""
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        issue, stock_balance_result = change_raw_material_issue_status_service(
            issue_id=issue_id,
            user=request.user
        )

        serialized_issue = RawMaterialIssueSerializer(issue)

        return JsonResponse({
            "result": "success",
            "message": f"Status updated to {issue.issue_status} successfully",
            "content": {
                "issue": serialized_issue.data,
                "stock_balance": stock_balance_result,
            }
        }, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({
            "result": "error",
            "message": "Resource not found",
            "content": ""
        }, status=status.HTTP_404_NOT_FOUND)

    except ValueError as e:
        return JsonResponse({
            "result": "error",
            "message": str(e),
            "content": ""
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error occurred while changing issue status: {e}")
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while changing issue status",
            "content": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", 'supervisor'])])
@transaction.atomic
def delete_raw_material_issue(request, issue_id):
    if not issue_id:
        return JsonResponse({
            "result": "error",
            "message": "Issue id is required",
            "content": ""
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Fetch non-approved issue
        issue = get_object_or_404(
            RawMaterialIssue.objects.exclude(issue_status=IssueStatus.APPROVED.value),
            _id=issue_id,
            is_deleted=False
        )

        requisition = issue.material_requisition
        # Add issued weight to the total requisition weight
        # requisition.total_requisition_quantity += issue.issue_weight ==> because actual substraction implemented on logic level
        requisition.save()
        issue.delete()

        return JsonResponse({
            "result": "success",
            "message": "Raw material issue deleted successfully",
            "_id": issue_id
        }, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({
            "result": "error",
            "message": "Issue is not found"
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error(f"Error occurred while deleting issue: {e}")
        return JsonResponse({
            "result": "error",
            "message": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

"""
=================== Report Methods =======================
"""
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def material_requisition_report(request):
    """
    Material Requisition Plain Report
    """

    try:
        serializer = MaterialRequisitionReportSerializer(data=request.GET)

        if not serializer.is_valid():
            return JsonResponse(
                {
                    "result": "error",
                    "message": "Invalid filters",
                    "content": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        filters = serializer.validated_data

        queryset = filter_material_requisition_service(filters)

        # check whether the purpose is export or not
        export = filters.get("export")

        if export:
            serializer = MaterialRequisitionSerializer(queryset, many=True)
        else:
            serializer = material_requisition_pagination(request, queryset)

        return JsonResponse(
            {
                "result": "success",
                "message": "Material requisition report fetched successfully",
                "content": serializer.data
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error occurred while fetching material requisition report: {e}")
        return JsonResponse(
            {
                "result": "error",
                "message": "Failed to fetch material requisition report",
                "content": str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def material_issue_report(request):
    """
    Raw Material Issue Report (Paginated)
    """

    try:
        serializer = RawMaterialIssueReportSerializer(data=request.GET)

        if not serializer.is_valid():
            return JsonResponse(
                {
                    "result": "error",
                    "message": "Invalid filters",
                    "content": serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        filters = serializer.validated_data

        queryset = filter_raw_material_issue_service(filters)

        # check whether the purpose is export or not
        export = filters.get("export")

        if export:
            serializer = RawMaterialIssueSerializer(queryset, many=True)
        else:
            serializer = raw_material_issue_pagination(request, queryset)

        return JsonResponse(
            {
                "result": "success",
                "message": "Raw material issue report fetched successfully",
                "content": serializer.data
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error occurred while fetching raw material issue report: {e}")
        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while fetching raw material issue report",
                "content": str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

"""
==================Additional Methods ======================
"""
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_plants(request):
    """
    Fetch all melting plants (no pagination).

    Returns JSON:
    [
        { "_id": "<uuid>", "plant_name": "Plant A" },
        { "_id": "<uuid>", "plant_name": "Plant B" }
    ]
    """
    try:
        plants = MeltingPlants.objects.filter(is_deleted=False).values(
            "_id",
            "plant_name"
        )

        # Convert QuerySet to a list of dicts
        plant_list = list(plants)

        return JsonResponse({
            "result": "success",
            "message": "Melting plants fetched successfully",
            "content": plant_list
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Failed to fetch melting plants: {str(e)}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to fetch melting plants: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

