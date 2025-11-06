from django.db.models import Q
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
        rate = Rate.objects.filter(status="active")
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
    """Fetch archived rates with pagination."""
    try :
        material_type = request.GET.get("material_type")
        _status = request.GET.get("status")
        expired_date = request.GET.get("expiry_date")
        
        # Start with all rates
        rates = Rate.objects.all()
        
        # Apply filters conditionally
        if material_type:
            rates = rates.filter(material_type__iexact=material_type)
        if _status:
            rates = rates.filter(status__iexact=_status)
        if expired_date:
            rates = rates.filter(expired_date__iexact=expired_date)

        rates = rates.order_by("-record_time")
        paginated_grn = rate_pagination(request, rates)
        material_types = MaterialType.get_material_types()
        return JsonResponse({
            "result" : "success",
            "data" : paginated_grn.data,
            "material_types": material_types
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Error occurred while fetching rates: %s", e)
        return JsonResponse({
            "result" : "error",
            "message" : "Error occurred while fetching rates"
        }, status=status.HTTP_400_BAD_REQUEST)
@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "manager"])])
def add_rate(request):
    """Add or update rate."""
    if request.method == "POST" or request.method == "PATCH":
        material_type = request.POST.get("material_type").strip().lower()
        heavy_rate = request.POST.get("heavy_rate").strip()
        medium_rate = request.POST.get("medium_rate").strip()
        light_rate = request.POST.get("light_rate").strip()
        fixed_rate = request.POST.get("fixed_rate").strip()

        if not material_type:
            return JsonResponse({"result": "error", "message": "material type not specified"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_valid_material(material_type):
            return JsonResponse({"result": "error", "message": "Selected material type is not available"}, status=status.HTTP_400_BAD_REQUEST)
        match material_type:
            case MaterialType.SCRAP.value:
                fixed_rate = None
                for rate, label in zip([heavy_rate, medium_rate, light_rate], ["heavy", "medium", "light"]):
                    if not is_valid_number(rate):
                        return JsonResponse({"result": "error", "message": f"{label} rate is invalid"}, status=status.HTTP_400_BAD_REQUEST)
            case _:
                heavy_rate = medium_rate = light_rate = None
                if not (fixed_rate or is_valid_number(fixed_rate)):
                    return JsonResponse({"result": "error", "message": "Fixed rate is invalid"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            today_rate = Rate.objects.filter(Q(material_type__iexact=material_type) & Q(created_at=today))
            if today_rate.exists():
                today_rate.update(
                    heavy_rate=heavy_rate, medium_rate=medium_rate, light_rate=light_rate,
                    fixed_rate=fixed_rate, status="active", updated_by=request.user.username, updated_at=today, record_time=timezone.now()
                )
            else:
                Rate.objects.create(
                    material_type=material_type, heavy_rate=heavy_rate, medium_rate=medium_rate,
                    light_rate=light_rate, fixed_rate=fixed_rate, status="active", created_by=request.user.username,
                    created_at=today, updated_by=request.user.username, updated_at=today
                )
            Rate.objects.filter(material_type__iexact=material_type).exclude(created_at=today).update(status="expired", expired_date=today, record_time=timezone.now())
            return JsonResponse({
                "result": "success",
                "message": "Material type rate added successfully"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error occurred while adding rate: %s ", e)
            return JsonResponse({"result": "error", "message": "Error occurred while adding rate"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "manager"])])
def delete_rate(request):
    """Delete a rate if it is not active."""
    if request.method == "DELETE":
        rate_id = request.POST.get('_id').strip()
        
        if not is_valid_uuid(rate_id):
            return JsonResponse({"result": "error", "message": "Not valid Rate ID"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            get_rate = get_object_or_404(Rate.all_objects, _id=rate_id)
            get_rate.delete()
            return JsonResponse({"result": "success", "message": f"Rate record is deleted successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while deleting record: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while deleting record"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "manager"])])
def restore_rate(request):
    if request.method == "PATCH":
        rate_id = request.POST.get('_id').strip()
        
        if not is_valid_uuid(rate_id):
            return JsonResponse({"result": "error", "message": "Not valid Rate ID"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            get_rate = get_object_or_404(Rate.all_objects, _id=rate_id, is_deleted=True)
            get_rate.restore()
            return JsonResponse({"result": "success", "message": f"Rate record is restored successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while restoring record: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while restoring record"}, status=status.HTTP_400_BAD_REQUEST)