import logging

from django.db import transaction
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from grn.models import GRN
from helperFunctions.pagination import customer_pagination
from helperFunctions.validations import is_valid_uuid
from utils.permissions import role_required
from .models import PurchaseCustomer
from .serializers import PurchaseCustomerCreateSerializer, PurchaseCustomerUpdateSerializer, CustomerPaymentSerializer, \
    GRNSerializer, PurchaseCustomerReportFilterSerializer, CustomerSerializer
from .services import generate_purchase_customer_plain_report, generate_purchase_customer_aggregated_report

logger = logging.getLogger(__name__)
# Create your views here.
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def get_customers(request):
    try:
        customers = PurchaseCustomer.objects.all().order_by("-record_time")
        paginated_customers = customer_pagination(request, customers)

        return JsonResponse({
            "result": "success",
            "data": paginated_customers.data
        })
    except Exception as e:
        logger.error("Error occurred while fetching customers: %s", e)
        return JsonResponse({
            "result": "error",
            "data": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchase_head", "supervisor", "manager"])])
def add_customer(request):
    try:
        serializer = PurchaseCustomerCreateSerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return JsonResponse(
                {
                    "result": "success", "message": "Customer registered successfully", "data": serializer.data},
                status=status.HTTP_201_CREATED
            )

        return JsonResponse(
            {
                "result": "error", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return JsonResponse(
            {"result": "error", "message": "Operation failed", "content": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['PUT'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchase_head", "supervisor", "manager"])])
def edit_customer(request, customer_id):
    try:
        customer = get_object_or_404(PurchaseCustomer, _id=customer_id)

        serializer = PurchaseCustomerUpdateSerializer(
            customer,
            data=request.data,
            partial=True,
            context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return JsonResponse(
                {"result": "success", "message": "Customer updated successfully", "data": serializer.data},
                status=status.HTTP_200_OK
            )

        return JsonResponse(
            {"result": "error", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Http404:
        return JsonResponse(
            {"result": "error", "message": "Customer not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error("Error occurred while updating customer: %s", e)
        return JsonResponse(
            {"result": "error", "message": "Operation failed"},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def filter_customer_tin(request):
    tin = request.query_params.get("tin")

    if not tin:
        return JsonResponse(
            {"result": "error", "message": "TIN not provided"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        customer = get_object_or_404(PurchaseCustomer.objects, TIN=tin)
        grns = GRN.objects.filter(customer=customer.TIN)
        totals = {
            "total_net_weight": sum(float(grn.net_weight or 0) for grn in grns),
            "total_net_price": sum(float(grn.net_price or 0) for grn in grns),
            "total_heavy_weight": sum(float(grn.heavy_grade or 0) for grn in grns),
            "total_medium_weight": sum(float(grn.medium_grade or 0) for grn in grns),
            "total_light_weight": sum(float(grn.light_grade or 0) for grn in grns),
        }
        context = {
            "grns": GRNSerializer(grns, many=True).data,
            "total_net_weight": totals["total_net_weight"] or 0,
            "total_net_price": totals["total_net_price"] or 0,
            "total_heavy_weight": totals["total_heavy_weight"] or 0,
            "total_medium_weight": totals["total_medium_weight"] or 0,
            "total_light_weight": totals["total_light_weight"] or 0,
            "paid_amount": customer.paid_amount,
            "remaining_payment": customer.remaining_amount,
        }

        return JsonResponse(
            {"result": "success", "data": context},
            status=status.HTTP_200_OK
        )
    except Http404:
        return JsonResponse(
            {"result": "error", "message": "Customer not found"},
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "finance"])])
@transaction.atomic
def pay_customer(request):
    serializer = CustomerPaymentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    tin = serializer.validated_data['tin']
    record_nos = serializer.validated_data['record_nos']

    try:
        customer = get_object_or_404(PurchaseCustomer, TIN=tin)
        grns = GRN.objects.filter(record_no__in=record_nos).exclude(status='paid')

        if not grns.exists():
            return JsonResponse({"result": "error", "message": "No unpaid records found for the given record numbers"},
                            status=status.HTTP_400_BAD_REQUEST)

        total_payment = sum(float(grn.net_price or 0) for grn in grns)

        if total_payment > customer.remaining_amount:
            return JsonResponse({"result": "error", "message": "Total payment exceeds customer's available balance"},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            customer.paid_amount += total_payment
            customer.remaining_amount -= total_payment
            customer.save()

            grns.update(status='paid')

            return JsonResponse({
                "result": "success",
                "message": f"Payment of {total_payment} successful for {grns.count()} records."
            }, status=status.HTTP_200_OK)

    except Http404:
        return JsonResponse({"result": "error", "message": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Error occurred while paying customer: %s", e)
        return JsonResponse({"result": "error", "message": "Operation failed"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
@transaction.atomic
def delete_customer(request, customer_id):
    if not is_valid_uuid(customer_id):
        return JsonResponse(
            {"result": "error", "message": "Invalid customer ID"},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        customer = get_object_or_404(PurchaseCustomer, _id=customer_id)
        # Delete customer
        customer.delete()

        return JsonResponse(
            {"result": "success", "message": "Customer deleted successfully"},
            status=status.HTTP_200_OK
        )
    except Http404:
        return JsonResponse(
            {"result": "error", "message": "Customer not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error("Error occurred while deleting customer: %s", e)
        return JsonResponse({"result": "error", "message": "Operation failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def purchase_customer_report(request):
    """
    Purchase Customer Plain Report
    Filter:
        - TIN
    """

    serializer = PurchaseCustomerReportFilterSerializer(data=request.GET)

    if not serializer.is_valid():
        return JsonResponse({
            "result": "error",
            "message": "Invalid filter parameters",
            "content": "Please provide valid TIN."
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        filters = serializer.validated_data

        report = generate_purchase_customer_plain_report(filters)

        export = serializer.validated_data.get("export")
        if export:
            paginated_result = CustomerSerializer(report["records"], many=True)
        else:
            paginated_result = customer_pagination(request, report["records"])

        return JsonResponse({
            "result": "success",
            "message": "Report generated successfully",
            "content": {
                "summary": {
                    "total_customers": report["totals"]["total_customers"] or 0,
                    "total_paid_amount": report["totals"]["total_paid_amount"] or 0,
                    "total_remaining_amount": report["totals"]["total_remaining_amount"] or 0,
                },
                "records": paginated_result.data,
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while generating purchase customer plain report: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Failed to generate report",
            "content": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def purchase_customer_aggregated_report(request):
    """
    Purchase Customer Aggregated Report
    Grouped By:
        - TIN
    """

    serializer = PurchaseCustomerReportFilterSerializer(data=request.GET)

    if not serializer.is_valid():
        return JsonResponse({
            "result": "error",
            "message": "Invalid filter parameters"
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        filters = serializer.validated_data

        report = generate_purchase_customer_aggregated_report(filters)

        return JsonResponse({
            "result": "success",
            "message": "Report generated successfully",
            "content": {
                "summary": {
                    "total_customers": report["totals"]["total_customers"] or 0,
                    "total_paid_amount": report["totals"]["total_paid_amount"] or 0,
                    "total_remaining_amount": report["totals"]["total_remaining_amount"] or 0,
                },
                "records": report["records"]
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while generating purchase customer aggregated report: %s", e)

        return JsonResponse({
            "result": "error",
            "message": "Failed to generate report",
            "content": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
