from datetime import datetime
from django.db.models import Q
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from utils.permissions import role_required
from grn.models import GRN
from .models import Customer
from .serializers import CustomerSerializer

# Create your views here.
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def get_customers(request):
    try:
        customers = Customer.objects.all()
        serializer = CustomerSerializer(customers, many=True)
        return JsonResponse({
            "result": "success",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "data": e
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchase_head", "supervisor", "manager"])])
def add_customer(request):
    if request.method == "POST":
        fname = request.POST.get("fname")
        lname = request.POST.get("lname")
        phone = request.POST.get("phone")
        email = request.POST.get("email").lower()
        tin = request.POST.get("tin")
        business_name = request.POST.get("business_name").lower()

        try:
            if Customer.objects.filter(TIN=tin).exists():
                return JsonResponse({"result": "error", "message": "Tin already exists"}, status=status.HTTP_400_BAD_REQUEST)
            if Customer.objects.filter(business_name=business_name).exists():
                return JsonResponse({"result": "error", "message": "business name already exists"}, status=status.HTTP_400_BAD_REQUEST)

            today = datetime.today().strftime("%Y-%m-%d")
            customer = Customer(
                fname=fname,
                lname=lname,
                phone=phone,
                email=email,
                TIN=tin,
                business_name=business_name,
                created_by=request.user.username,
                created_at=today,
                updated_by=request.user.username,
                updated_at=today
            )
            customer.save()
            # calculate remaining amount of this customer if the TIN found in GRN record
            grn = GRN.objects.filter(customer=tin).all()
            _customer = Customer.objects.get(TIN=tin)
            total_net_price = 0
            for grn in grn:
                total_net_price = float(total_net_price) + float(grn.net_price)
            if _customer is not None:
                _customer.remaining_amount = float(total_net_price)
                _customer.save()
            return JsonResponse({"result": "success", "message": "Customer is registered successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({"result": "error", "message": "Error occurred while adding customer"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchase_head", "supervisor", "manager"])])
def edit_customer(request):
    if request.method == "PATCH":
        _id = request.POST.get("_id")
        fname = request.POST.get("fname")
        lname = request.POST.get("lname")
        phone = request.POST.get("phone")
        email = request.POST.get("email").lower()
        tin = request.POST.get("tin")
        business_name = request.POST.get("business_name").lower()

        try:
            if not Customer.objects.filter(_id=_id).exists():
                return JsonResponse({"result": "error", "message": "Customer not found"}, status=status.HTTP_400_BAD_REQUEST)
            if Customer.objects.filter(Q(TIN=tin), ~Q(_id=_id)).exists():
                return JsonResponse({"result": "error", "message": "Tin is already used"}, status=status.HTTP_400_BAD_REQUEST)
            if Customer.objects.filter(Q(business_name=business_name), ~Q(_id=_id)).exists():
                return JsonResponse({"result": "error", "message": "Business_name is already used"}, status=status.HTTP_400_BAD_REQUEST)

            today = datetime.today().strftime("%Y-%m-%d")
            customer = Customer.objects.filter(_id=_id).first()
            if fname != '':
                customer.fname = fname
            if lname != '':
                customer.lname = lname
            if email != '':
                customer.email = email
            if phone != '':
                customer.phone = phone
            if tin != '':
                customer.TIN = tin
            if business_name != '':
                customer.business_name = business_name
            customer.updated_at = today
            customer.updated_by = request.user.username
            customer.save()
            return JsonResponse({"result": "success", "message": "Customer updated successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({"result": "error", "message": 'Error occurred while updating customer'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def filter_customer_TIN(request):
    tin = request.query_params.get("tin", "")
    try:
        if not tin: return JsonResponse({"result": "error", "message": "TIN not provided"}, status=status.HTTP_400_BAD_REQUEST)
        customer = Customer.objects.get(TIN=tin)
        if customer is None:
            return JsonResponse({
                "result": "error",
                "message": "Customer not found"
            }, status=status.HTTP_400_BAD_REQUEST)
        context = {
            "total_net_weight": 0,
            "total_net_price": 0,
            "total_heavy_weight": 0,
            "total_medium_weight": 0,
            "total_light_weight": 0,
            "paid_amount": customer.paid_amount,
            "remaining_payment": customer.remaining_amount
        }
        grn = GRN.objects.filter(customer=customer.TIN).all()
        for grn in grn:
            context["total_net_weight"] = context['total_net_weight'] + float(grn.net_weight)
            context["total_net_price"] = context['total_net_price'] + float(grn.net_price)
            context["total_heavy_weight"] = context['total_heavy_weight'] + float(grn.heavy_grade)
            context["total_medium_weight"] = context['total_medium_weight'] + float(grn.medium_grade)
            context["total_light_weight"] = context['total_light_weight'] + float(grn.light_grade)
        return JsonResponse({"result": "success", "data": context}, status=status.HTTP_200_OK)
    except Exception as e:
        return JsonResponse({"result": "error", "message": "operation failed"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "finance"])])
def pay_customer(request):
    if request.method == "POST":
        tin = request.POST.get("tin")
        record_no = request.POST.get("record_no")

        try:
            customer = Customer.objects.get(TIN=tin)
            grn = GRN.objects.get(record_no=record_no)
            if customer is None: return JsonResponse({"result": "error", "message": "Customer not found"}, status=status.HTTP_400_BAD_REQUEST)
            if grn is None: return JsonResponse({"result": "error", "message": "Record not found"}, status=status.HTTP_400_BAD_REQUEST)
            if float(grn.net_price) > customer.remaining_amount: return JsonResponse(
                {"result": "error", "message": "Paid amount exceeds available balance"}, status=status.HTTP_400_BAD_REQUEST)
            # pay the customer
            customer.paid_amount = customer.paid_amount + float(grn.net_price)
            customer.remaining_amount = customer.remaining_amount - float(grn.net_price)
            customer.save()
            grn.status = "paid"
            grn.save()
            return JsonResponse({"result": "success", "message": 'Payment is successful'}, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({"result": "error", "message": "Operation failed"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def delete_customer(request):
    if request.method == "DELETE":
        tin = request.POST.get("tin")
        try:
            if not Customer.objects.filter(TIN=tin).exists():
                return JsonResponse({"result": "error", "message": "Customer not found"}, status=status.HTTP_400_BAD_REQUEST)
            GRN.objects.filter(customer=tin).all().delete()
            Customer.objects.filter(TIN=tin).delete()
            return JsonResponse({"result": "success", "message": "Customer deleted successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return JsonResponse({"result": "error", "message": "operation failed"}, status=status.HTTP_400_BAD_REQUEST)
