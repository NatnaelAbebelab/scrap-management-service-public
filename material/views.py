import logging
from datetime import datetime

from django.db import models, transaction
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import permission_classes, api_view
from rest_framework.permissions import IsAuthenticated

from helperFunctions.pagination import material_requisition_pagination, raw_material_issue_pagination, melting_plants_pagination
from material.enums import Plants, RequisitionStatus, IssueStatus
from material.report import MaterialRequisitionFilter, RawMaterialIssueFilter
from material.models import MaterialRequisition, MaterialRequisitionItem, RawMaterialIssue, MeltingPlants
from material.serializers import MaterialRequisitionSerializer, RawMaterialIssueSerializer, ApprovedMaterialRequisitionSerializer, MeltingPlantsSerializer
from stock.models import CumulativeBalance
from stock.views import add_transport_balance

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

        return JsonResponse({"result": "success", "message": "fetched successfully", "content": serialized_melting_plants.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "data": e
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_melting_plant(request):
    """
    Expected request.data format:
    {
        "plant": "OLD_PLANT",
    }
    """
    try:
        user = request.user
        data = request.data

        plant_value = data.get("plant")
        # Ensure the value is valid
        if not plant_value:
            return JsonResponse({"result": "error", "message": "plant is required", "content": ""}, status=status.HTTP_400_BAD_REQUEST)

        # Create Melting Plant
        melting_plant = MeltingPlants.objects.create(
            plant_name=plant_value,
            created_by=user.username,
            created_by_id=user,
            created_at=today,
            updated_at=today,
        )
        melting_plant.save()
        serialized_melting_plant = MeltingPlantsSerializer(melting_plant)

        return JsonResponse({
            "result": "success",
            "message": "Melting plant is created successfully",
            "content": serialized_melting_plant.data
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while creating melting plant",
            "content": str(e)},
            status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def edit_melting_plant(request):
    """
        Expected request.data format:
        {
            "_id": "3f2f1a4c-9416-4a0a-8ae4-859e7e45ac7c",
            "new_name": "OLD_PLANT",
        }
    """
    try:
        data = request.data
        user = request.user

        melting_plant_id = data.get("_id")
        if not melting_plant_id:
            return JsonResponse({"result": "error", "message": "_id is required", "content": ""}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch existing melting plant
        melting_plant = MeltingPlants.objects.get(_id=melting_plant_id)

        # Update main fields
        assign_if_not_empty(melting_plant, "plant_name", data.get("new_name"))

        melting_plant.updated_by = user.username
        melting_plant.updated_by_id = user
        melting_plant.updated_at = today
        melting_plant.save()
        serialized_melting_plant = MeltingPlantsSerializer(melting_plant)

        return JsonResponse({
            "result": "success",
            "message": "Melting plant is updated successfully",
            "content": serialized_melting_plant.data
        }, status=status.HTTP_200_OK)

    except MeltingPlants.DoesNotExist:
            return JsonResponse({
                "result": "error",
                "message": "Melting plant is not found",
                "content": ""
            }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while updating melting plant",
            "content": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_melting_plant(request, melting_plant_id):
    try:
        melting_plant_id = get_object_or_404(MeltingPlants.objects, _id=melting_plant_id)
        melting_plant_id.delete()

        return JsonResponse({"result": "success", "message": "Melting plant is deleted successfully", "content": ""},
                            status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({"result": "error", "message": "Melting plant is not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse({"result": "error", "message": "Error occurred while deleting melting plant", "content": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_material_requisitions(request):
    try:
        user = request.user
        material_requisitions = MaterialRequisition.objects.filter(
            created_by_id=user,
            is_deleted=False
        ).order_by('-record_time')

        serialized_requisition = material_requisition_pagination(request, material_requisitions)

        return JsonResponse({"result": "success", "message": "fetched successfully", "content": serialized_requisition.data}, status=status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "data": e
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_material_requisition(request, requisition_id):
    try:
        requisition = get_object_or_404(MaterialRequisition, _id=requisition_id, is_deleted=False)
        serializer = MaterialRequisitionSerializer(requisition)
        return JsonResponse({"result": "success", "message": "fetched successfully", "content": serializer.data}, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({"result": "error", "message": "Resource not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse(
            {"result": "error", "message": "An error occurred", "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_approved_material_requisitions(request):
    approved_reqs = MaterialRequisition.objects.filter(
        requisition_status=RequisitionStatus.APPROVED.value,
        is_deleted=False
    ).order_by('-record_time')

    serializer = ApprovedMaterialRequisitionSerializer(approved_reqs, many=True)
    return JsonResponse({
        "result": "success",
        "message": "Approved material requisitions loaded successfully",
        "content": serializer.data
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_material_requisition(request):
    """
    Expected request.data format:
    {
        "plant": "3f2f1a4c-9416-4a0a-8ae4-859e7e45ac7c",
        "requisition_date": "2025-11-25",
        "requisition_no": "REQ-001",
        "items": [
            {"item_code": "IT001", "item_name": "Item 1", "quantity": 5, "unit_price": 10.5},
            {"item_code": "IT002", "item_name": "Item 2", "quantity": 2, "unit_price": 20.0}
        ]
    }
    """
    try:
        user = request.user
        data = request.data

        plant = data.get("plant")
        # Ensure the value is valid
        if not plant:
            return JsonResponse({"result": "error", "message": "Melting plant is required", "content": ""}, status=status.HTTP_400_BAD_REQUEST)

        active_balance = CumulativeBalance.objects.filter(is_active=True, is_deleted=False).first()
        current_balance = float(active_balance.current_balance) if active_balance.current_balance else 0.0

        melting_plant = get_object_or_404(MeltingPlants, _id=plant)
        # Create Material Requisition
        requisition = MaterialRequisition.objects.create(
            melting_plant=melting_plant,
            requisition_date=data.get("requisition_date"),
            requisition_no=data.get("requisition_no"),
            created_by=user.username,
            created_by_id=user,
            created_at=today,
            updated_at=today,
        )

        total_requisition_quantity = 0
        total_requisition_price = 0
        items_data = data.get("items", [])
        for item_data in items_data:
            quantity = float(item_data.get("quantity", 0))
            unit_price = float(item_data.get("unit_price", 0))
            total_price = quantity * unit_price
            total_requisition_quantity += quantity

            if total_requisition_quantity > current_balance:
                return JsonResponse({
                    "result": "error",
                    "message": "Total requisition quantity exceeds the current balance",
                    "content": ""
                }, status=status.HTTP_400_BAD_REQUEST)

            MaterialRequisitionItem.objects.create(
                material_requisition=requisition,
                item_code=item_data.get("item_code"),
                item_name=item_data.get("item_name"),
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price
            )
            total_requisition_price += total_price

        # Update total requisition
        requisition.total_requisition_quantity = total_requisition_quantity
        requisition.total_requisition_price = total_requisition_price
        requisition.save()

        serialized_requisition = MaterialRequisitionSerializer(requisition)

        return JsonResponse({
            "result": "success",
            "message": "Material requisition created successfully",
            "content": serialized_requisition.data
        }, status=status.HTTP_201_CREATED)

    except Http404:
        return JsonResponse({"result": "error", "message": "Melting plant not found", "content": ""}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "data": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def edit_material_requisition(request):
    """
        Expected request.data format:
        {
            "_id": "3f2f1a4c-9416-4a0a-8ae4-859e7e45ac7c",
            "plant": "3f2f1a4c-9416-4a0a-8ae4-859e7e45ac7c",
            "requisition_date": "2025-11-25",
            "requisition_no": "REQ-001",
            "items": [
                {"item_code": "IT001", "item_name": "Item 1", "quantity": 5, "unit_price": 10.5},
                {"item_code": "IT002", "item_name": "Item 2", "quantity": 2, "unit_price": 20.0}
            ]
        }
    """
    try:
        data = request.data
        user = request.user

        requisition_id = data.get("_id")
        plant = data.get("plant")
        if not requisition_id:
            return JsonResponse({"result": "error", "message": "_id is required", "content": ""}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch existing requisition
        requisition = MaterialRequisition.objects.get(_id=requisition_id, is_deleted=False)
        # Update main fields
        assign_if_not_empty(requisition, "requisition_date", data.get("requisition_date"))
        assign_if_not_empty(requisition, "requisition_no", data.get("requisition_no"))

        if plant:
            melting_plant = get_object_or_404(MeltingPlants, _id=plant)
            requisition.melting_plant = melting_plant

        requisition.updated_by = user.username
        requisition.updated_by_id = user
        requisition.updated_at = today
        requisition.save()

        # Handle items update
        received_items = data.get("items", [])
        existing_items = {str(i._id): i for i in requisition.items.all()}

        new_total = 0
        received_ids = []

        for item_data in received_items:
            item_id = item_data.get("_id")

            quantity = float(item_data.get("quantity", 0))
            unit_price = float(item_data.get("unit_price", 0))
            total_price = quantity * unit_price

            # Update existing item
            if item_id and item_id in existing_items:
                item = existing_items[item_id]
                item.item_code = item_data.get("item_code", item.item_code)
                item.item_name = item_data.get("item_name", item.item_name)
                item.quantity = quantity
                item.unit_price = unit_price
                item.total_price = total_price
                item.save()

                received_ids.append(item_id)

            else:
                # Create a new item
                MaterialRequisitionItem.objects.create(
                    material_requisition=requisition,
                    item_code=item_data.get("item_code", ""),
                    item_name=item_data.get("item_name", ""),
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price
                )

            new_total += total_price

        # Delete removed items
        for item_id, item in existing_items.items():
            if item_id not in received_ids:
                item.delete()

        # Update total requisition
        requisition.total_requisition = new_total
        requisition.save()

        serialized_requisition = MaterialRequisitionSerializer(requisition)

        return JsonResponse({
            "result": "success",
            "message": "Material requisition updated successfully",
            "content": serialized_requisition.data
        }, status=status.HTTP_200_OK)

    except MaterialRequisition.DoesNotExist:
            return JsonResponse({
                "result": "error",
                "message": "Material requisition not found",
                "content": ""
            }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def approve_material_requisition(request, requisition_id):
    try:
        requisition = MaterialRequisition.objects.get(_id=requisition_id)
        requisition.requisition_status = RequisitionStatus.APPROVED.value
        requisition.updated_by = request.user.username
        requisition.updated_by_id = request.user
        requisition.updated_at = today
        requisition.save()

        serialized_requisition = MaterialRequisitionSerializer(requisition)

        return JsonResponse({"result": "success", "message": "Material requisition approved successfully", "content": serialized_requisition.data},
                            status=status.HTTP_200_OK)

    except MaterialRequisition.DoesNotExist:
        return JsonResponse({"result": "error", "message": "Material requisition not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse({"result": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_material_requisition(request, requisition_id):
    with transaction.atomic():
        try:
            user = request.user
            requisition = get_object_or_404(MaterialRequisition.objects, _id=requisition_id)

            #Check if there is atleast one approved issue for the requisition
            approved_issues = RawMaterialIssue.objects.filter(
                material_requisition=requisition,
                is_deleted=False,
                issue_status=IssueStatus.APPROVED.value
            )
            if approved_issues.exists():
                return JsonResponse({
                    "result": "error",
                    "message": "Cannot delete requisition with approved issues",
                    "approved_issue_count": approved_issues.count()
                }, status=status.HTTP_400_BAD_REQUEST)

            # Change the issue weight of all non-approved issues, which is in turn all issues are either new or issued
            all_issues = RawMaterialIssue.objects.filter(
                material_requisition=requisition,
                is_deleted=False
            )
            if all_issues.exists():
                all_issues.update(
                    issue_weight=0.0,
                    material_requisition=None,
                    updated_by=user.username,
                    updated_by_id=user,
                    updated_at=today
                )

            requisition.delete()

            return JsonResponse({"result": "success", "message": "Material requisition is deleted successfully", "content": ""},
                                status=status.HTTP_200_OK)

        except Http404:
            return JsonResponse({"result": "error", "message": "Material requisition not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return JsonResponse({"result": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_raw_material_issues(request):
    try:
        user = request.user
        issues = RawMaterialIssue.objects.filter(
            created_by_id=user,
            is_deleted=False
        ).order_by('-record_time')

        serialized_raw_material_issue = raw_material_issue_pagination(request, issues)

        return JsonResponse(
            {"result": "success", "message": "fetched successfully", "content": serialized_raw_material_issue.data},
            status=status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "data": e
        }, status=status.HTTP_400_BAD_REQUEST)

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
        return JsonResponse({"result": "error", "message": "Resource not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse({"result": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_raw_material_issue(request):
    """
        Expected request.data format:
        {
            "material_requisition": "uuid-of-requisition",
            "issue_weight": 2000,
            "issue_date": "2025-11-25",
            "issue_no": "ISSUE-001",
            "issue_status": "NEW"
        }
    """
    try:
        user = request.user
        data = request.data

        requisition_id = data.get("material_requisition")
        issue_weight = data.get("issue_weight")

        if not requisition_id:
            return JsonResponse({"result": "error", "message": "material_requisition is required", "content": ""}, status=status.HTTP_400_BAD_REQUEST)
        if not issue_weight:
            return JsonResponse({"result": "error", "message": "Issue weight is required", "content": ""}, status=status.HTTP_400_BAD_REQUEST)
        # Fetch the requisition
        requisition = get_object_or_404(MaterialRequisition, _id=requisition_id)

        if float(issue_weight) > requisition.total_requisition_quantity:
            return JsonResponse({"result": "error", "message": "Issue weight cannot be greater than total requisition quantity"}, status=status.HTTP_400_BAD_REQUEST)

        # Since there is issue weight, which has impacts on weight manipulation
        total_issued = RawMaterialIssue.objects.filter(
            material_requisition=requisition,
            is_deleted=False
        ).aggregate(total=models.Sum('issue_weight'))['total'] or 0.0

        remaining = requisition.total_requisition_quantity - total_issued

        # Check whether all amounts of the requisition had been issued
        if requisition.total_requisition_quantity == total_issued:
            return JsonResponse({"result": "success", "message": "All amounts of the requisition had been issued", "content": ""}, status=status.HTTP_200_OK)

        # Check if issue weight exceeds remaining
        if issue_weight > remaining:
            return JsonResponse({"result": "error", "message": "Issue weight exceeds remaining quantity", "content": ""}, status=status.HTTP_400_BAD_REQUEST)

        # Create Raw Material Issue
        issue = RawMaterialIssue.objects.create(
            material_requisition=requisition,
            issue_date=data.get("issue_date", ""),
            issue_no=data.get("issue_no", ""),
            issue_weight=float(issue_weight),
            created_by=user.username,
            created_by_id=user,
            created_at=today,
            updated_by=user.username,
            updated_by_id=user,
            updated_at=today
        )
        issue.save()

        serialized_issue = RawMaterialIssueSerializer(issue)

        return JsonResponse({
            "result": "success",
            "message": "Raw Material issue created successfully",
            "content": serialized_issue.data
        }, status=status.HTTP_201_CREATED)

    except Http404:
        return JsonResponse({"result": "error", "message": "Material Requisition not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while creating material issue",
            "content": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def edit_raw_material_issue(request):
    """
        Expected request.data format:
        {
            "_id": "uuid-of-issue",
            "material_requisition": "uuid-of-requisition",
            "issue_date": "2025-11-26",
            "issue_no": "ISSUE-002",
            "issue_weight: 2000
        }
    """
    try:
        data = request.data
        user = request.user
        issue_id = data.get("_id")

        if not issue_id:
            return JsonResponse({"result": "error", "message": "Raw material issue is required"}, status=status.HTTP_400_BAD_REQUEST)

        issue_weight = data.get("issue_weight")
        issue = get_object_or_404(RawMaterialIssue, _id=issue_id, is_deleted=False)
        material_requisition_id = data.get("material_requisition")
        if material_requisition_id not in [None, ""]:
            requisition = get_object_or_404(MaterialRequisition, _id=material_requisition_id)

            total_issued = RawMaterialIssue.objects.filter(
                material_requisition=requisition,
                is_deleted=False
            ).aggregate(total=models.Sum('issue_weight'))['total'] or 0.0

            remaining = requisition.total_requisition_quantity - total_issued

            # Check whether all amounts of the requisition had been issued
            if requisition.total_requisition_quantity == total_issued:
                return JsonResponse(
                    {"result": "error", "message": "All amounts of the requisition had been issued", "content": ""},
                    status=status.HTTP_400_BAD_REQUEST)

            # Check if issue weight exceeds remaining
            if issue_weight and issue_weight > remaining: # new issue_weight
                return JsonResponse(
                    {"result": "error", "message": "Issue weight exceeds remaining quantity", "content": ""},
                    status=status.HTTP_400_BAD_REQUEST)

            if issue.issue_weight > remaining:
                return JsonResponse(
                    {"result": "error", "message": "Issue weight exceeds remaining quantity", "content": ""},
                    status=status.HTTP_400_BAD_REQUEST)

            issue.material_requisition = requisition

        # Update other fields
        assign_if_not_empty(issue, "issue_date", data.get("issue_date"))
        assign_if_not_empty(issue, "issue_no", data.get("issue_no"))
        assign_if_not_empty(issue, "issue_weight", issue_weight)

        # Update audit fields
        issue.updated_by = user.username
        issue.updated_by_id = user
        issue.updated_at = today
        issue.save()

        serialized_issue = RawMaterialIssueSerializer(issue)

        return JsonResponse({
            "result": "success",
            "message": "Raw Material issue updated successfully",
            "content": serialized_issue.data
        }, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({"result": "error", "message": "Resource is not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse({"result": "error", "message": "Error occurred while editing issue", "data": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def change_raw_material_issue_status(request, issue_id):
    with transaction.atomic():
        try:
            stock_balance_result = None

            if not issue_id:
                return JsonResponse({
                    "result": "error",
                    "message": "Issue id is required",
                    "content": ""
                }, status=status.HTTP_400_BAD_REQUEST)

            issue = get_object_or_404(RawMaterialIssue, _id=issue_id, is_deleted=False)

            if issue.issue_status == IssueStatus.NEW.value:
                new_status = IssueStatus.ISSUED.value

            elif issue.issue_status == IssueStatus.ISSUED.value:
                new_status = IssueStatus.APPROVED.value
                total_transport_weight = issue.issue_weight

                stock_balance_result = add_transport_balance(
                    total_transport_weight=total_transport_weight,
                    request=request,
                    issue_date=issue.issue_date,
                    issue_no=issue.issue_no
                )

            else:
                return JsonResponse({
                    "result": "error",
                    "message": f"Cannot change status from '{issue.issue_status}'",
                    "content": ""
                }, status=status.HTTP_400_BAD_REQUEST)

            issue.issue_status = new_status
            issue.updated_by = request.user.username
            issue.updated_by_id = request.user
            issue.updated_at = today
            issue.save()

            serialized_issue = RawMaterialIssueSerializer(issue)

            response_data = {
                "result": "success",
                "message": f"Status updated to {new_status}",
                "content": serialized_issue.data,
            }

            if stock_balance_result:
                response_data["stock_balance"] = stock_balance_result

            return JsonResponse(response_data, status=status.HTTP_200_OK)

        except Http404:
            return JsonResponse({
                "result": "error",
                "message": "Resource is not found"
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"Error occurred while changing issue status: {e}")
            return JsonResponse({
                "result": "error",
                "message": "Error occurred while changing issue status",
                "content": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_raw_material_issue(request, issue_id):
    with transaction.atomic():
        try:
            if not issue_id:
                return JsonResponse({
                    "result": "error",
                    "message": "Issue id is required",
                    "content": ""
                }, status=status.HTTP_400_BAD_REQUEST)

            # Fetch issue that is not already deleted
            issue = get_object_or_404(RawMaterialIssue, _id=issue_id, is_deleted=False)
            if issue.issue_status == IssueStatus.APPROVED.value:
                return JsonResponse({
                    "result": "error",
                    "message": "Cannot delete an approved issue",
                    "content": ""
                }, status=status.HTTP_400_BAD_REQUEST)

            requisition = issue.material_requisition
            # Add issued weight to the total requisition weight
            requisition.total_requisition_quantity += issue.issue_weight
            requisition.save()
            issue.delete()

            return JsonResponse({
                "result": "success",
                "message": "Raw material issue deleted successfully",
                "_id": issue_id
            }, status=status.HTTP_200_OK)

        except Http404:
            return JsonResponse({"result": "error", "message": "Resource is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return JsonResponse({
                "result": "error",
                "message": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

"""
=================== Report Methods =======================
"""
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def material_requisition_report(request):
    with transaction.atomic():
        try:
            """
               Get paginated material requisition report with filters

               Expected request body:
               {
                   "requisition_no": "REQ-001",
                   "requisition_start_date": "2024-01-01",
                   "requisition_start_date": "2024-12-31",
                   "melting_plant": "3f2f1a4c-9416-4a0a-8ae4-859e7e45ac7c",
                   "min_quantity": 10,
                   "max_quantity": 100,
                   "status": "approved",
               }
            """

            filters = {
                'requisition_no': request.GET.get('requisition_no'),
                'requisition_start_date': request.GET.get('requisition_start_date'),
                'requisition_end_date': request.GET.get('requisition_end_date'),
                'melting_plant': request.GET.get('melting_plant'),
                'min_quantity': request.GET.get('min_quantity'),
                'max_quantity': request.GET.get('max_quantity'),
                'requisition_status': request.GET.get('status')
            }

            base_queryset = MaterialRequisition.objects.select_related(
                'melting_plant', 'created_by_id', 'updated_by_id'
            ).prefetch_related('items')

            filtered_queryset = MaterialRequisitionFilter.apply_filters(
                base_queryset, filters
            )

            serialized_requisition = material_requisition_pagination(request, filtered_queryset)
            return JsonResponse(
                {"result": "success", "message": "fetched successfully", "content": serialized_requisition.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return JsonResponse({
                "result": "error",
                "message": "Error occurred while fetching material requisition report",
                "content": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_material_requisition_report(request):
    with transaction.atomic():
        try:
            """
               Get paginated material requisition report with filters

               Expected request body:
               {
                   "requisition_no": "REQ-001",
                   "requisition_start_date": "2024-01-01",
                   "requisition_start_date": "2024-12-31",
                   "melting_plant": "3f2f1a4c-9416-4a0a-8ae4-859e7e45ac7c",
                   "min_quantity": 10,
                   "max_quantity": 100,
                   "status": "approved",
               }
            """

            filters = {
                'requisition_no': request.GET.get('requisition_no'),
                'requisition_start_date': request.GET.get('requisition_start_date'),
                'requisition_end_date': request.GET.get('requisition_end_date'),
                'melting_plant': request.GET.get('melting_plant'),
                'min_quantity': request.GET.get('min_quantity'),
                'max_quantity': request.GET.get('max_quantity'),
                'requisition_status': request.GET.get('status')
            }

            base_queryset = MaterialRequisition.objects.select_related(
                'melting_plant', 'created_by_id', 'updated_by_id'
            ).prefetch_related('items')

            filtered_queryset = MaterialRequisitionFilter.apply_filters(
                base_queryset, filters
            )

            serialized_requisition = MaterialRequisitionSerializer(filtered_queryset, many=True)

            return JsonResponse(
                {"result": "success", "message": "fetched successfully", "content": serialized_requisition.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return JsonResponse({
                "result": "error",
                "message": "Error occurred while fetching material requisition report",
                "content": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def material_issue_report(request):
    with transaction.atomic():
        try:
            """
            Get paginated raw material issue report with filters

            Expected query parameters:
            {
                "issue_no": "ISSUE-001",
                "issue_start_date": "2024-01-01",
                "issue_end_date": "2024-12-31",
                "issue_status": "issued",
                "min_weight": 10,
                "max_weight": 100
            }
            """

            filters = {
                'issue_no': request.GET.get('issue_no'),
                'issue_start_date': request.GET.get('issue_start_date'),
                'issue_end_date': request.GET.get('issue_end_date'),
                'issue_status': request.GET.get('issue_status'),
                'min_weight': request.GET.get('min_weight'),
                'max_weight': request.GET.get('max_weight'),
            }

            # Get base queryset with related data
            base_queryset = RawMaterialIssue.objects.select_related(
                'material_requisition',
                'material_requisition__melting_plant',
                'created_by_id',
                'updated_by_id'
            )

            # Apply filters
            filtered_queryset = RawMaterialIssueFilter.apply_filters(
                base_queryset, filters
            )

            # Create pagination function similar to material_requisition_pagination
            serialized_issues = raw_material_issue_pagination(request, filtered_queryset)

            return JsonResponse(
                {"result": "success", "message": "Raw material issue report fetched successfully",
                 "content": serialized_issues.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return JsonResponse({
                "result": "error",
                "message": "Error occurred while fetching raw material issue report",
                "content": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_material_issue_report(request):
    with transaction.atomic():
        try:
            """
            Get paginated raw material issue report with filters

            Expected query parameters:
            {
                "issue_no": "ISSUE-001",
                "issue_start_date": "2024-01-01",
                "issue_end_date": "2024-12-31",
                "issue_status": "issued",
                "min_weight": 10,
                "max_weight": 100
            }
            """

            filters = {
                'issue_no': request.GET.get('issue_no'),
                'issue_start_date': request.GET.get('issue_start_date'),
                'issue_end_date': request.GET.get('issue_end_date'),
                'issue_status': request.GET.get('issue_status'),
                'min_weight': request.GET.get('min_weight'),
                'max_weight': request.GET.get('max_weight'),
            }

            # Get base queryset with related data
            base_queryset = RawMaterialIssue.objects.select_related(
                'material_requisition',
                'material_requisition__melting_plant',
                'created_by_id',
                'updated_by_id'
            )

            # Apply filters
            filtered_queryset = RawMaterialIssueFilter.apply_filters(
                base_queryset, filters
            )

            serialized_issues = RawMaterialIssueSerializer(filtered_queryset, many=True)

            return JsonResponse(
                {"result": "success", "message": "Raw material issue report fetched successfully",
                 "content": serialized_issues.data},
                status=status.HTTP_200_OK)

        except Exception as e:
            return JsonResponse({
                "result": "error",
                "message": "Error occurred while fetching raw material issue report",
                "content": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

"""
==================Additional Methods ======================
"""
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_plants(request):
    """
    Returns:
    [
        { "value": "old_plant", "label": "Old Plant" },
        { "value": "new_plant", "label": "New Plant" }
    ]
    """
    try:
        plants = [
            {
                "value": plant.value,
                "label": plant.name.replace("_", " ").title()
            }
            for plant in Plants
        ]

        return JsonResponse({
            "result": "success",
            "message": "Plants fetched successfully",
            "content": plants
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

