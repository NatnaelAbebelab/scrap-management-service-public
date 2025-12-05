import logging
from datetime import datetime

from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import permission_classes, api_view
from rest_framework.permissions import IsAuthenticated

from helperFunctions.pagination import material_requisition_pagination, raw_material_issue_pagination
from material.enums import Plants, RequisitionStatus, IssueStatus
from material.models import MaterialRequisition, MaterialRequisitionItem, RawMaterialIssue
from material.serializers import MaterialRequisitionSerializer, RawMaterialIssueSerializer, ApprovedMaterialRequisitionSerializer

# Create your views here.
logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')

def assign_if_not_empty(instance, field, value):
    if value not in [None, ""]:
        setattr(instance, field, value)

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
        "plant": "OLD_PLANT",
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

        plant_value = data.get("plant", Plants.OLD_PLANT.value)
        # Ensure the value is valid
        if plant_value.lower() not in [p.value for p in Plants]:
            return JsonResponse({
                "result": "error",
                "data": f"Invalid plant value: {plant_value}"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create Material Requisition
        requisition = MaterialRequisition.objects.create(
            plant=plant_value,
            requisition_date=data.get("requisition_date"),
            requisition_no=data.get("requisition_no"),
            created_by=user.username,
            created_by_id=user,
            created_at=today,
            updated_at=today,
        )

        total_requisition = 0
        items_data = data.get("items", [])
        for item_data in items_data:
            quantity = float(item_data.get("quantity", 0))
            unit_price = float(item_data.get("unit_price", 0))
            total_price = quantity * unit_price

            MaterialRequisitionItem.objects.create(
                material_requisition=requisition,
                item_code=item_data.get("item_code"),
                item_name=item_data.get("item_name"),
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price
            )
            total_requisition += total_price

        # Update total requisition
        requisition.total_requisition = total_requisition
        requisition.save()

        serialized_requisition = MaterialRequisitionSerializer(requisition)

        return JsonResponse({
            "result": "success",
            "message": "Material requisition created successfully",
            "content": serialized_requisition.data
        }, status=status.HTTP_201_CREATED)

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
            "plant": "OLD_PLANT",
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
        if not requisition_id:
            return JsonResponse({"result": "error", "message": "_id is required", "content": ""}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch existing requisition
        requisition = MaterialRequisition.objects.get(_id=requisition_id, is_deleted=False)
        # Update main fields
        assign_if_not_empty(requisition, "plant", data.get("plant"))
        assign_if_not_empty(requisition, "requisition_date", data.get("requisition_date"))
        assign_if_not_empty(requisition, "requisition_no", data.get("requisition_no"))

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
    try:
        requisition = get_object_or_404(MaterialRequisition.objects, _id=requisition_id)
        requisition.delete()

        return JsonResponse({"result": "success", "message": "Material requisition deleted successfully", "content": ""},
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
        "issue_date": "2025-11-25",
        "issue_no": "ISSUE-001",
        "issue_status": "NEW"
    }
    """
    try:
        user = request.user
        data = request.data

        requisition_id = data.get("material_requisition")
        if not requisition_id:
            return JsonResponse({"result": "error", "message": "material_requisition is required", "content": ""}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch the requisition
        requisition = get_object_or_404(MaterialRequisition, _id=requisition_id)

        # Create Raw Material Issue
        issue = RawMaterialIssue.objects.create(
            material_requisition=requisition,
            issue_date=data.get("issue_date", ""),
            issue_no=data.get("issue_no", ""),
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
            "data": str(e)
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
    }
    """
    try:
        data = request.data
        user = request.user
        issue_id = data.get("_id")

        if not issue_id:
            return JsonResponse({"result": "error", "message": "Raw material issue is required"}, status=status.HTTP_400_BAD_REQUEST)

        issue = get_object_or_404(RawMaterialIssue, _id=issue_id, is_deleted=False)
        material_requisition_id = data.get("material_requisition")
        if material_requisition_id not in [None, ""]:
            requisition = get_object_or_404(MaterialRequisition, _id=material_requisition_id)
            issue.material_requisition = requisition
        # Update other fields
        assign_if_not_empty(issue, "issue_date", data.get("issue_date"))
        assign_if_not_empty(issue, "issue_no", data.get("issue_no"))

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
    try:
        if not issue_id:
            return JsonResponse({
                "result": "error",
                "message": "issue_id is required",
                "content": ""
            }, status=status.HTTP_400_BAD_REQUEST)

        issue = get_object_or_404(RawMaterialIssue, _id=issue_id, is_deleted=False)

        # Status transition logic
        if issue.issue_status == IssueStatus.NEW.value:
            new_status = IssueStatus.ISSUED.value

        elif issue.issue_status == IssueStatus.ISSUED.value:
            new_status = IssueStatus.APPROVED.value

        else:
            return JsonResponse({
                "result": "error",
                "message": f"Cannot change status from '{issue.issue_status}'",
                "content": ""
            }, status=status.HTTP_400_BAD_REQUEST)

        # Apply update
        issue.issue_status = new_status
        issue.updated_by = request.user.username
        issue.updated_by_id = request.user
        issue.updated_at = today
        issue.save()

        serialized_issue = RawMaterialIssueSerializer(issue)

        return JsonResponse({
            "result": "success",
            "message": f"Status updated to {new_status}",
            "content": serialized_issue.data
        }, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({"result": "error", "message": "Resource is not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_raw_material_issue(request, issue_id):
    try:
        if not issue_id:
            return JsonResponse({
                "result": "error",
                "message": "issue_id is required",
                "content": ""
            }, status=status.HTTP_400_BAD_REQUEST)

        # Fetch issue that is not already deleted
        issue = get_object_or_404(RawMaterialIssue, _id=issue_id, is_deleted=False)
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

