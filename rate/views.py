from django.db import transaction
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Rate
from helperFunctions.material_type import *
from helperFunctions.grade_type import *
from helperFunctions.validations import *
from helperFunctions.pagination import *
from helperFunctions.status import *
from utils.permissions import role_required
from .serializers import RateSerializer
from datetime import datetime
import logging
# Create your views here.

logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')

@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def get_active_rate(request):
    """Fetch an active rate."""
    try:
        rate = get_object_or_404(Rate.objects.get_active_items(), status="active")
        serializer = RateSerializer(rate, many=True)
        return JsonResponse({
            "result": "success",
            "message": "Active rate is fetched successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Error occurred while fetching active rate: %s ", e)
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while fetching active rate"
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "finance", "manager"])])
def get_rate_archive(request):
    try:
        # Validate query params with serializer
        serializer = RateFilterSerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        # Base queryset: include all non-deleted rates
        rates = Rate.all_objects.filter(is_deleted=False)

        # Apply filters conditionally
        if filters.get("created_from"):
            created_from = filters["created_from"].strftime("%Y-%m-%d")
            rates = rates.filter(created_at__gte=created_from)

        if filters.get("created_to"):
            created_to = filters["created_to"].strftime("%Y-%m-%d")
            rates = rates.filter(created_at__lte=created_to)

        if filters.get("expired_from"):
            expired_from = filters["expired_from"].strftime("%Y-%m-%d")
            rates = rates.filter(expired_date__gte=expired_from)

        if filters.get("expired_to"):
            expired_to = filters["expired_to"].strftime("%Y-%m-%d")
            rates = rates.filter(expired_date__lte=expired_to)

        # Order by latest first
        rates = rates.order_by("-record_time")

        # Paginate
        paginated_rates = rate_pagination(request, rates)

        # Material types for front-end
        material_types = MaterialType.get_material_types()

        return JsonResponse({
            "result": "success",
            "data": paginated_rates.data,
            "material_types": material_types
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while fetching rates: %s", e)
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while fetching rates"
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "manager"])])
@transaction.atomic
def add_or_update_rate(request):
    serializer = AddRateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    material_type = data['material_type'].strip().lower()
    heavy_rate = data.get('heavy_rate')
    medium_rate = data.get('medium_rate')
    light_rate = data.get('light_rate')
    fixed_rate = data.get('fixed_rate')

    # Validate material type
    if not material_type:
        return JsonResponse({"result": "error", "message": "Material type not specified"}, status=status.HTTP_400_BAD_REQUEST)
    if not is_valid_material(material_type):
        return JsonResponse({"result": "error", "message": "Selected material type is not available"}, status=status.HTTP_400_BAD_REQUEST)

    # Validate rates
    if material_type == MaterialType.SCRAP.value:
        fixed_rate = None
        for rate, label in zip([heavy_rate, medium_rate, light_rate], ["heavy", "medium", "light"]):
            if not is_valid_number(rate):
                return JsonResponse({"result": "error", "message": f"{label} rate is invalid"}, status=status.HTTP_400_BAD_REQUEST)
    else:
        heavy_rate = medium_rate = light_rate = None
        if not (fixed_rate and is_valid_number(fixed_rate)):
            return JsonResponse({"result": "error", "message": "Fixed rate is invalid"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Update today's rate if exists, else create
        today_rate_qs = Rate.objects.filter(Q(material_type__iexact=material_type) & Q(created_at=today))
        if today_rate_qs.exists():
            today_rate_qs.update(
                heavy_rate=heavy_rate,
                medium_rate=medium_rate,
                light_rate=light_rate,
                fixed_rate=fixed_rate,
                status="active",
                updated_by=request.user.username,
                updated_at=today,
                record_time=timezone.now()
            )
        else:
            Rate.objects.create(
                material_type=material_type,
                heavy_rate=heavy_rate,
                medium_rate=medium_rate,
                light_rate=light_rate,
                fixed_rate=fixed_rate,
                status="active",
                created_by=request.user.username,
                created_at=today,
                updated_by=request.user.username,
                updated_at=today
            )

        # Expire old rates in a single query
        Rate.objects.filter(material_type__iexact=material_type).exclude(created_at=today).update(
            status="expired",
            expired_date=today,
            record_time=timezone.now()
        )

        return JsonResponse({"result": "success", "message": "Material type rate added successfully"}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while adding rate: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while adding rate"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "manager"])])
def delete_rate(request, rate_id):
    """Delete a rate if it is not active."""
    if not is_valid_uuid(rate_id):
        return JsonResponse({"result": "error", "message": "Not valid Rate ID"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        get_rate = get_object_or_404(Rate.objects.get_active_items(), _id=rate_id)
        get_rate.delete()
        return JsonResponse({"result": "success", "message": "Rate deleted successfully"}, status=status.HTTP_200_OK)
    except Http404:
        return JsonResponse({"result": "error", "message": "Rate not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Error occurred while deleting rate: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while deleting rate"}, status=status.HTTP_400_BAD_REQUEST)