from cmath import exp

from django.conf import settings
from django.http import JsonResponse, Http404
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime, date
from django.utils.timezone import now
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rate.models import Rate
from helperFunctions.material_type import *
from helperFunctions.grade_type import *
from customer.models import PurchaseCustomer
from helperFunctions.validations import *
from helperFunctions.pagination import *
from helperFunctions.status import *
from helperFunctions.roles import *
from stock.views import add_purchase_stock
from .models import GRN, GRNSerialNumber
from django.db.models import Q
from utils.permissions import role_required
from utils.exceptions import *
from utils.grade_parser import parse_scrap_grade
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd
import re, uuid, os, logging

from .service import increment_grn_serial_number, filter_grn_service

# Create your views here.

logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')

def extract_grade(content) :
    results = {}
    if "&" in content:
        grade_name = {
            "H": "HEAVY",
            "M": "MEDIUM",
            "L": "LIGHT"
        }
        parts = content.split("&")
        for part in parts:
            part = part.strip().upper()
            if "%" in part:
                value, grade = part.split("%")
                if is_valid_grade(grade):
                    results[grade] = value
    else:
        first_char = [char for char in content.strip()]
        results = {"grade": first_char[0]}
        
    return results
def filter_grn(role, tin, material_type, plate_no, start_date, end_date, status):
    """
    Function to filter GRN based on parameters
    """
    allowed_status = Status.get_status_by_role(role)
    if status and status not in allowed_status:
        raise StatusException(f"{status} is not belong to {role}")
    try:
        # Base QuerySet
        grn_records = GRN.objects.all().order_by("-record_time")
        
        # Filter by TIN (Check if tin exists in Customer model)
        if tin and clean_tin(tin):
            customer = PurchaseCustomer.objects.filter(TIN=tin).first()
            if customer:
                grn_records = grn_records.filter(customer=tin)
        
        # Filter by material type
        if material_type and is_valid_material(material_type):
            grn_records = grn_records.filter(material_type__iexact=material_type)
        
        grn_records = grn_records.annotate(
            casted_first_date=ToDate("first_date")
        )
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            grn_records = grn_records.filter(casted_first_date__gte=start_date)
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            grn_records = grn_records.filter(casted_first_date__lte=end_date)
        
        if plate_no:
            grn_records = grn_records.filter(plate_no__iexact=plate_no)
        
        # Filter by status
        if status:
            grn_records = grn_records.filter(status=status)
        else:
            grn_records = grn_records.filter(status__in=allowed_status)
        
        return grn_records
    except Exception as e:
        logger.error("Error occurred while filtering grn: %s", e)
        raise FilterException("Error occurred while filtering grn", data=GRN.objects.none())
def get_daily_performance(role, tin, material_type, start_date, end_date, plate_no, status):
    """
    Function to filter GRN based on parameters
    """
    allowed_status = Status.get_status_by_role(role)
    if status and status not in allowed_status:
        raise StatusException(f"{status} is not belong to {role}")
    try:
        # Base QuerySet
        grn_records = GRN.objects.all().order_by("-record_time")
        
        # Filter by TIN (Check if tin exists in Customer model)
        if tin and clean_tin(tin):
            customer = PurchaseCustomer.objects.filter(TIN=tin).first()
            if customer:
                grn_records = grn_records.filter(customer=tin)
        
        # Filter by material type
        if material_type and is_valid_material(material_type):
            grn_records = grn_records.filter(material_type__iexact=material_type)
        
        grn_records = grn_records.annotate(
            casted_first_date=ToDate("first_date")
        )
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            grn_records = grn_records.filter(casted_first_date__gte=start_date)
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            grn_records = grn_records.filter(casted_first_date__lte=end_date)
        
        if plate_no:
            grn_records = grn_records.filter(plate_no__iexact=plate_no)
        
        # Filter by status
        if status:
            grn_records = grn_records.filter(status=status)
        else:
            grn_records = grn_records.filter(status__in=allowed_status)
          
        return grn_records
    except Exception as e:
        logger.error("Error occurred while calculating daily purchase performance: %s", e)
        raise DailyPerformanceException("Error occurred while calculating daily purchase performance", data=GRN.objects.none())

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "weight_man", "purchaser"])])
def upload_csv_file(request):
    csv_file = request.FILES.get("csv_file")
    rate_date = request.POST.get("date", today)  # YYYY-MM-DD

    skipped_records = {"invalid_records_no": [], "invalid_firm": [], "invalid_material_type": []}

    if not rate_date or not is_valid_date(rate_date):
        return JsonResponse({"result": "error", "message": "Provide valid date"}, status=400)

    if not csv_file or not csv_file.name.endswith(".xlsx"):
        return JsonResponse({"result": "error", "message": "Invalid file format"}, status=400)

    try:
        df = pd.read_excel(csv_file, engine="openpyxl")
        required_columns = ["RECORD NO", "MATERIAL", "FIRM", "NET", "DATE1"]
        df.dropna(subset=required_columns, inplace=True)
        records = df.to_dict(orient="records")

        # -------------------------
        # Preload Rates (cache)
        # -------------------------
        rate_cache = {}
        for r in Rate.objects.filter(is_deleted=False):
            mat_type = r.material_type.lower()
            if mat_type == "scrap":
                rate_cache[mat_type] = {
                    "H": float(r.heavy_rate or 0),
                    "M": float(r.medium_rate or 0),
                    "L": float(r.light_rate or 0),
                }
            else:
                rate_cache[mat_type] = float(r.fixed_rate or 0)

        # -------------------------
        # Preload Customers
        # -------------------------
        all_tins = {clean_tin(str(r.get("FIRM", "")).strip()) for r in records}
        customer_cache = {c.TIN: c for c in PurchaseCustomer.objects.filter(TIN__in=all_tins)}

        # -------------------------
        # Prepare Bulk Inserts
        # -------------------------
        grn_bulk = []
        new_customers_bulk = []
        total_purchase_weight = {}

        for record in records:
            try:
                record_no = str(record.get("RECORD NO", "")).strip()
                if not record_no:
                    skipped_records["invalid_records_no"].append(record_no)
                    continue

                firm = str(record.get("FIRM", "")).strip()
                if not firm or not is_valid_number(firm):
                    skipped_records["invalid_firm"].append(record_no)
                    continue

                material_raw = str(record.get("MATERIAL", "")).strip()
                net_weight = float(record.get("NET", 0))
                if net_weight <= 0:
                    skipped_records["invalid_records_no"].append(record_no)
                    continue

                # -------------------------
                # Initialize grade and rate
                # -------------------------
                grade = {"H": 0.0, "M": 0.0, "L": 0.0}
                used_rate = {"H": 0.0, "M": 0.0, "L": 0.0, "F": 0.0}
                net_price = 0
                material_type = None

                # -------------------------
                # SCRAP
                # -------------------------
                scrap_match = re.search(r'SCRAP \{(.*?)}', material_raw.upper())
                if scrap_match:
                    material_type = "scrap"
                    scrap_rates = rate_cache.get("scrap")
                    if not scrap_rates:
                        skipped_records["invalid_material_type"].append(record_no)
                        continue

                    grade_result = extract_grade(scrap_match.group(1))
                    if not grade_result:
                        skipped_records["invalid_material_type"].append(record_no)
                        continue

                    if "grade" in grade_result:
                        g = grade_result["grade"].upper()
                        grade[g] = net_weight
                        used_rate[g] = scrap_rates[g]
                        net_price = grade[g] * scrap_rates[g]
                    else:
                        for k, pct in grade_result.items():
                            k = k.upper()
                            grade[k] = (float(pct) / 100) * net_weight
                            used_rate[k] = scrap_rates[k]
                            net_price += grade[k] * scrap_rates[k]

                # -------------------------
                # NON-SCRAP
                # -------------------------
                else:
                    material_type = material_raw.lower()
                    if not is_valid_material(material_type) or material_type == "scrap":
                        skipped_records["invalid_material_type"].append(record_no)
                        continue

                    fixed_rate = rate_cache.get(material_type)
                    if not fixed_rate:
                        skipped_records["invalid_material_type"].append(record_no)
                        continue

                    used_rate["F"] = fixed_rate
                    net_price = net_weight * fixed_rate

                # -------------------------
                # GRN Object
                # -------------------------
                customer_tin = clean_tin(firm)
                serial_number = increment_grn_serial_number()

                grn_bulk.append(
                    GRN(
                        record_no=record_no,
                        plate_no=record.get("PLATE NO"),
                        first_weight=record.get("1ST WEIGHING"),
                        first_date=record.get("DATE1"),
                        second_weight=record.get("2ND WEIGHING"),
                        net_weight=net_weight,
                        customer=customer_tin,
                        material_type=MaterialType[material_type.upper()].value,
                        heavy_grade=grade["H"],
                        medium_grade=grade["M"],
                        light_grade=grade["L"],
                        heavy_rate=used_rate["H"],
                        medium_rate=used_rate["M"],
                        light_rate=used_rate["L"],
                        fixed_rate=used_rate["F"],
                        serial_no=serial_number,
                        net_price=round(net_price, 2),
                        status="new",
                        created_by=request.user.username,
                        updated_by=request.user.username,
                    )
                )

                # -------------------------
                # Stock Map
                # -------------------------
                date_key = record.get("DATE1")
                total_purchase_weight.setdefault(date_key, {"purchase_weight": 0.0, "transport_weight": 0.0})
                total_purchase_weight[date_key]["purchase_weight"] += net_weight

                # -------------------------
                # Customer Update
                # -------------------------
                customer = customer_cache.get(customer_tin)
                if customer:
                    customer.remaining_amount += round(net_price, 2)
                else:
                    new_cust = PurchaseCustomer(
                        TIN=customer_tin,
                        remaining_amount=round(net_price, 2),
                        created_by=request.user.username,
                        updated_by=request.user.username
                    )
                    customer_cache[customer_tin] = new_cust
                    new_customers_bulk.append(new_cust)

            except Exception as e:
                logger.error("Error processing record %s: %s", record.get("RECORD NO"), e)
                skipped_records["invalid_records_no"].append(record.get("RECORD NO"))
                continue

        # -------------------------
        # Bulk Insert
        # -------------------------
        GRN.objects.bulk_create(grn_bulk, batch_size=500)
        if new_customers_bulk:
            PurchaseCustomer.objects.bulk_create(new_customers_bulk, batch_size=200)
        if customer_cache:
            PurchaseCustomer.objects.bulk_update(customer_cache.values(), ["remaining_amount"])

        stock_balance = add_purchase_stock(total_purchase_weight, request)

        return JsonResponse({
            "result": "success",
            "message": "File uploaded successfully",
            "skipped_records": skipped_records,
            "total_inserted": len(grn_bulk),
            "stock_balance": stock_balance,
        }, status=200)

    except Exception as e:
        logger.error("Error uploading CSV: %s", e)
        return JsonResponse({"result": "error", "message": "Error uploading file"}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "weight_man", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def get_grn(request):
    try:
        serializer = GRNFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        role = get_user_role(request.user)

        grn_all = GRN.objects.all()
        total_records_count = grn_all.count()
        approved_records_count = grn_all.filter(status="approved").count()
        paid_records_count = grn_all.filter(status="paid").count()
        other_records_count = grn_all.exclude(status__in=["approved", "paid"]).count()

        # --- Filter GRN using service ---
        grn_qs = filter_grn_service(
            role=role,
            tin=filters.get("tin"),
            material_type=filters.get("material_type"),
            plate_no=filters.get("plate_no"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            status=filters.get("status")
        )

        # --- Paginate results ---
        paginated_grn = grn_pagination(request, grn_qs)

        material_types = MaterialType.get_material_types()
        status_list = Status.get_status_by_role_object(role)

        return JsonResponse({
            "result": "success",
            "data": paginated_grn.data,
            "totalRecordsCount": total_records_count,
            "approvedRecordsCount": approved_records_count,
            "paidRecordsCount": paid_records_count,
            "otherRecordsCount": other_records_count,
            "material_types": material_types,
            "status_list": status_list
        })

    except Exception as e:
        logger.error("Error fetching GRN: %s", e)
        return JsonResponse({"result": "error", "message": "Error fetching GRN"}, status=400)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def change_grn_status_bulk(request):
    """
    Based on the role of logged user change the status of grn to expected ones.
    Roles are ===> Purchaser, Inspector, Purchase head, Supervisor
    """
    if request.method == "PATCH":
        record_nos = request.POST.getlist("record_nos")
        target_status = request.POST.get("target_status").strip().lower()
        
        if not record_nos:
            return JsonResponse({"result": "error", "message": "Provide record numbers of records to apply status change"}, status=status.HTTP_400_BAD_REQUEST)
        valid_record_no = [n for n in record_nos if is_digit(n)]
        role = get_user_role(request.user)
        allowed_status = Status.get_status_by_role(role)
        # filter grn by record no
        try:
            if target_status in allowed_status and target_status not in ["new", "declined", "pending"]:
                change_status = Status.get_previous_status(Status.get_status(target_status).status_value)
                skipped_records = GRN.objects.filter(Q(record_no__in=valid_record_no) & ~Q(status=target_status)).exclude(Q(status=change_status)).values("record_no")
                GRN.objects.filter(Q(record_no__in=valid_record_no) & Q(status=change_status)).update(
                    status=Status.get_status(target_status).status_value, 
                    updated_by=request.user.username, 
                    updated_at=today,
                    record_time=timezone.now())
                return JsonResponse({"result": "success", "message": f"Bulk record's status changed successfully", "skipped_records": list(skipped_records)}, status=status.HTTP_200_OK)
            return JsonResponse({"result": "error", "message": "Given status is not allowed within your role"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Error occurred while changing status: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while changing status"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def change_grn_status_individual(request):
    """
    Change individual GRN record's status and Here also consider Role
    """
    if request.method == "PATCH":
        record_no = request.POST.get("record_no").strip()
        target_status = request.POST.get("target_status").strip().lower()
        
        role = get_user_role(request.user)
        if not record_no:
            return JsonResponse({"result": "error", "message": "Provide record no to change status"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_digit(record_no):
            return JsonResponse({"result": "error", "message": "Record number must be digits only"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            get_grn = GRN.objects.filter(record_no=record_no).first()
            if get_grn:
                if role == "supervisor":
                    get_grn.status = Status.get_status(target_status).status_value 
                    get_grn.updated_by = request.user.username
                    get_grn.updated_at = today
                    get_grn.save()
                    return JsonResponse({"result": "success", "message": f"Record {record_no} status is changed successfully"}, status=status.HTTP_200_OK)
                
                # get available status for the role
                allowed_status = Status.get_status_by_role(role)
                if target_status in allowed_status and target_status not in ["new", "declined", "pending"]:
                    change_status = Status.get_previous_status(Status.get_status(target_status).status_value)
                    if get_grn.status == change_status or get_grn.status == target_status:
                        get_grn.status = Status.get_status(target_status).status_value 
                        get_grn.updated_by = request.user.username
                        get_grn.updated_at = today
                        get_grn.save()
                        return JsonResponse({"result": "success", "message": f"Record {record_no} status is changed successfully"}, status=status.HTTP_200_OK)
                    else:
                        return JsonResponse({"result": "error", "message": f"Record {record_no} is not belong to your scope"}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return JsonResponse({"result": "error", "message": f"Target status {target_status} is not allowed status for the role {role}"}, status=status.HTTP_400_BAD_REQUEST)
            return JsonResponse({"result": "error", "message": f"Record {record_no} is not found"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Error occurred while changing status: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while changing status"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["purchaser", "super_admin", "purchase_head", "supervisor"])]) #purchase_head
def approve_grn_supervisor(request) :
    if request.method == "PATCH":
        record_no = request.POST.get("record_no").strip()
        grn_no = request.POST.get("grn_no").strip()
        grn_img = request.FILES.get("grn_img")
        approve_img = request.FILES.get("approve_img")
        scale_img = request.FILES.get("scale_img")
        
        if not record_no:
            return JsonResponse({"result": "error", "message": "Provide record no to change status"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_digit(record_no):
            return JsonResponse({"result": "error", "message": "Record number must be digits only"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            get_grn = GRN.objects.filter(record_no=record_no).first()
            # let's get the role
            role = get_user_role(request.user)
            
            if role == "purchaser":
                # GRN number, GRN image, Scale image is required
                if grn_no and not(is_digit(grn_no)):
                    return JsonResponse({"result": "error", "message": "Provide valid GRN No"}, status=status.HTTP_400_BAD_REQUEST)
                #if not (scale_img): #grn_img and approve_img and 
                    #return JsonResponse({"result": "error", "message": "Scale proof image is not provided"}, status=status.HTTP_400_BAD_REQUEST)
                
                if GRN.all_objects.filter(grn_no=grn_no).first():
                    return JsonResponse({"result": "error", "message": "GRN No is already used"}, status=status.HTTP_400_BAD_REQUEST)
                # upload GRN image and Scale Image
                if get_grn:
                    # Save the files
                    if grn_img:
                        grn_file_name = str(uuid.uuid4())
                        grn_file_path = os.path.join(settings.MEDIA_ROOT, "grn-img", grn_file_name + "." + grn_img.name.split(".")[-1])
                        os.makedirs(os.path.dirname(grn_file_path), exist_ok=True)
                        with open(grn_file_path, 'wb+') as destination:
                            for chunk in grn_img.chunks():
                                destination.write(chunk)
                        get_grn.grn_img = grn_file_name + "." + grn_img.name.split(".")[-1]
                    
                    if scale_img:
                        scale_file_name = str(uuid.uuid4())
                        scale_file_path = os.path.join(settings.MEDIA_ROOT, "scale-img", scale_file_name + "." + scale_img.name.split(".")[-1])
                        os.makedirs(os.path.dirname(scale_file_path), exist_ok=True)
                        with open(scale_file_path, 'wb+') as destination:
                            for chunk in scale_img.chunks():
                                destination.write(chunk)
                        get_grn.scale_img = scale_file_name + "." + scale_img.name.split(".")[-1]
                    
                    get_grn.grn_no = grn_no
                    get_grn.status = Status.PREPARED.status_value
                    get_grn.updated_by = request.user.username
                    get_grn.updated_at = today
                    get_grn.save()
                    
                    return JsonResponse({"result": "success", "message": f"Record {record_no} status is prepared successfully"}, status=status.HTTP_200_OK)
                return JsonResponse({"result": "error", "message": f"There is no GRN record under {record_no}"}, status=status.HTTP_400_BAD_REQUEST)
            
            if role == "purchase_head":
                #if not (approve_img): #grn_img and approve_img and 
                    #return JsonResponse({"result": "error", "message": "Approve proof image is not provided"}, status=status.HTTP_400_BAD_REQUEST)
                if get_grn:
                    if approve_img:
                        approve_file_name = str(uuid.uuid4())
                        approve_file_path = os.path.join(settings.MEDIA_ROOT, "approve-img", approve_file_name + "." + approve_img.name.split(".")[-1])
                        os.makedirs(os.path.dirname(approve_file_path), exist_ok=True)
                        with open(approve_file_path, 'wb+') as destination:
                            for chunk in approve_img.chunks():
                                destination.write(chunk)
                        get_grn.approve_img = approve_file_name + "." + approve_img.name.split(".")[-1]
                        
                    get_grn.status = Status.VERIFIED.status_value
                    get_grn.updated_by = request.user.username
                    get_grn.updated_at = today
                    get_grn.save()
                    
                    return JsonResponse({"result": "success", "message": f"Record {record_no} status is verified successfully"}, status=status.HTTP_200_OK)
                return JsonResponse({"result": "error", "message": f"There is no GRN record under {record_no}"}, status=status.HTTP_400_BAD_REQUEST)
            return JsonResponse({"result": "error", "message": f"There is no GRN record under {record_no}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Error occurred while approving record: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while approving record"}, status=status.HTTP_400_BAD_REQUEST)    
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head"])])
def decline_grn(request):
    """
    Here this end point does change the status of record to previous one if the roles are:
    Purchaser <=== Inspector <=== Purchase head
    """
    if request.method == "PATCH":
        record_no = request.POST.get("record_no").strip()
        
        if not record_no:
            return JsonResponse({"result": "error", "message": "Provide record no to change status"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_digit(record_no):
            return JsonResponse({"result": "error", "message": "Record number must be digits only"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            get_grn = GRN.objects.filter(record_no=record_no).first()
            role = get_user_role(request.user)
            role_status = Status.get_status_by_role(role)
            if get_grn and (get_grn.status in role_status):
               current_status = get_grn.status
               _status = "declined"
               if Status.is_declined(_status):
                    # When declining, go back to the previous status
                    previous_status = Status.get_previous_status(current_status)
                    if previous_status:
                        get_grn.status = previous_status
                        get_grn.updated_by = request.user.username
                        get_grn.updated_at = today
                        get_grn.save()
                        return JsonResponse({"result": "success", "message": f"Status of {record_no} reverted to {previous_status}"}, status=status.HTTP_200_OK)
                    else:
                        return JsonResponse({"result": "error", "message": f"You can't decline this record {record_no}"}, status=status.HTTP_400_BAD_REQUEST)
            return JsonResponse({"result": "error", "message": f"Record {record_no} is not found or align with your scope"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Error occurred while changing the status: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while changing status"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def decline_grn_supervisor(request) :
    if request.method == "PATCH":
        record_no = request.POST.get("record_no").strip()
        
        if not record_no:
            return JsonResponse({"result": "error", "message": "Provide record no to change status"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_digit(record_no):
            return JsonResponse({"result": "error", "message": "Record number must be digits only"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            get_grn = GRN.objects.filter(record_no=record_no).first()
            _status = Status.get_status("declined")
            if get_grn:
                get_grn.status = _status.status_value
                get_grn.updated_by = request.user.username
                get_grn.updated_at = today
                get_grn.save()
                return JsonResponse({"result": "success", "message": "Record is declined successfully"}, status=status.HTTP_200_OK)
            return JsonResponse({"result": "error", "message": f"Record {record_no} is not found"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e :
            logger.error("Error occurred while declining record: %s", e)
            return JsonResponse({"result": "error", "message" : f"Error occurred while declining record {record_no}"}, status.HTTP_400_BAD_REQUEST)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def delete_grn(request) :
    if request.method == "DELETE":
        _id = request.POST.get("_id").strip()
        
        if not is_valid_uuid(_id):
            return JsonResponse({"result": "error", "message": "Not valid object ID"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            get_grn = get_object_or_404(GRN.all_objects, _id=_id)
            get_grn.delete()
            return JsonResponse({"result": "success", "message": f"Record is deleted successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while deleting record: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while deleting record"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def restore_grn(request) :
    if request.method == "PATCH":
        tin = request.POST.get("tin").strip()
        
        if not is_digit(tin):
            return JsonResponse({"result": "error", "message": f"TIN {tin} must be digits only"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            record_tin = clean_tin(tin)
            get_grn = get_object_or_404(GRN.all_objects, customer=record_tin, is_deleted=True)
            get_grn.restore()
            return JsonResponse({"result": "success", "message": f"Record is restored successfully"}, status=status.HTTP_200_OK)
        except ValueError:
            return JsonResponse({"result": "error", "message": f"TIN {tin} is not valid TIN"}, status=status.HTTP_400_BAD_REQUEST)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while restoring record: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while restoring record"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "finance"])])
def get_grn_finance(request) :
    tin = request.query_params.get("tin", "").strip()
    material_type = request.query_params.get("material_type", "").strip().lower()
    start_date = request.query_params.get("start_date", "").strip()
    end_date = request.query_params.get("end_date", "").strip()
    _status = request.query_params.get("status", "").strip().lower()
    
    if tin and not clean_tin(tin):
        return JsonResponse({"result": "error", "message": "TIN has no proper value"}, status=status.HTTP_400_BAD_REQUEST)
    if material_type and not is_valid_material(material_type):
        return JsonResponse({"result": "error", "message": "Material type is not valid"}, status=status.HTTP_400_BAD_REQUEST)
    if start_date and not is_valid_date(start_date):
        return JsonResponse({"result": "error", "message": "Start date is not valid"}, status=status.HTTP_400_BAD_REQUEST)
    if end_date and not is_valid_date(end_date):
        return JsonResponse({"result": "error", "message": "End date is not valid"}, status=status.HTTP_400_BAD_REQUEST)
    role = get_user_role(request.user)
    allowed_status = Status.get_status_by_role(role)
    if _status and _status not in allowed_status:
        return JsonResponse({"result": "error", "message": f"{_status} is not {role.upper()} scope"}, status=status.HTTP_400_BAD_REQUEST)
    
    try :
        # Base QuerySet
        grn_records = GRN.objects.all().order_by("-record_time")
        # Filter by TIN (Check if tin exists in Customer model)
        if tin and clean_tin(tin):
            customer = PurchaseCustomer.objects.filter(TIN=tin).first()
            if customer:
                grn_records = grn_records.filter(customer=tin)
        # Filter by material type
        if material_type:
            grn_records = grn_records.filter(material_type=material_type)
            
        grn_records = grn_records.annotate(
            casted_first_date=ToDate("first_date")
        )
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            grn_records = grn_records.filter(casted_first_date__gte=start_date)
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            grn_records = grn_records.filter(casted_first_date__lte=end_date)      
        # Filter by status
        if _status:
            grn_records = grn_records.filter(status=_status)
        else:
            grn_records = grn_records.filter(status__in=allowed_status)
        
        paginated_query = grn_pagination(request, grn_records)
        status_list = Status.get_status_by_role(role)
        return JsonResponse({"result": "success", "message": "GRNs are filtered successfully", "data": paginated_query.data, "status_list": status_list}, status=status.HTTP_200_OK)
    except ValueError:
        return JsonResponse({"result": "error", "message": f"TIN {tin} is invalid"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Error occurred while fetching records for the role: %s", e)
        return JsonResponse({"result": "error","message": "Error occurred while fetching records for the role"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "finance"])])
def pay_customer(request):
    """
    Pay customer for purchase processes ===> update the agency remaining amount and paid amount
    """
    if request.method == "POST":
        tin = request.POST.get("tin").strip()
        record_no = request.POST.get("record_no").strip()
        
        if not is_digit(record_no):
            return JsonResponse({"result": "error", "message": "Record no must be digits only"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tin = clean_tin(tin)
            customer = get_object_or_404(PurchaseCustomer.objects, TIN=tin)
            grn = get_object_or_404(GRN.objects, record_no=record_no)
            
            if float(grn.net_price) > float(customer.remaining_amount): 
                return JsonResponse({"result": "error", "message": "Paid amount exceeds available balance"}, status=status.HTTP_400_BAD_REQUEST)
            # pay the customer
            customer.paid_amount = Decimal(str(float(customer.paid_amount) + float(grn.net_price))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            customer.remaining_amount = Decimal(str(float(customer.remaining_amount) - float(grn.net_price))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            customer.updated_by = request.user.username
            customer.updated_at = today
            customer.save()
            
            grn.status = Status.get_status("paid").status_value
            grn.updated_by = request.user.username
            grn.updated_at = today
            grn.save()
            return JsonResponse({"result": "success", "message": "Payment is successful"}, status=status.HTTP_200_OK)
        except ValueError:
            return JsonResponse({"result": "error", "message": f"TIN {tin} is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while paying customer: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while paying customer"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def filter_grn_records(request):
    """
    Filter GRN records based on some filter criteria ==> TIN, Material Type, Plate_NO, Start Date, End Date, Status, Period
    """
    if request.method == "POST":
        tin = request.POST.get("tin", "").strip()
        material_type = request.POST.get("material_type", "").strip().lower()
        plate_no = request.POST.get("plate_no", "").strip()
        start_date = request.POST.get("start_date", "").strip()
        end_date = request.POST.get("end_date", "").strip()
        _status = request.POST.get("status", "").strip().lower()
        
        try:
            # get the role of the user
            role = get_user_role(request.user)
            filtered_grn = filter_grn(role, tin, material_type, plate_no, start_date, end_date, _status)
            paginated_query = grn_pagination(request, filtered_grn)
            status_list = Status.get_status_by_role(role)
            return JsonResponse({"result": "success", "message": "GRNs are filtered successfully", "data": paginated_query.data, "status_list": status_list}, status=status.HTTP_200_OK)
        except ValueError:
            return JsonResponse({"result": "error", "message": f"TIN {tin} is invalid"}, status=status.HTTP_400_BAD_REQUEST)
        except StatusException as e:
            return JsonResponse({"result": "error", "message": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except FilterException as e:
            return JsonResponse({"result": "error", "message": e.message, "data": e.data}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Error occurred while filtering grn %s:", e)
            return JsonResponse({"result": "error", "message": "Error occurred while filtering grn"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def get_daily_purchase_performance(request):
    """
    Get daily purchase performance
    """
    if request.method == "GET":
        tin = request.GET.get("tin", "").strip()
        material_type = request.GET.get("material_type", "").strip().lower()
        plate_no = request.GET.get("plate_no", "").strip()
        start_date = request.GET.get("start_date", "").strip()
        end_date = request.GET.get("end_date", "").strip()
        _status = request.GET.get("status", "").strip().lower()
        
        if not start_date:
            start_date = date.today().strftime("%Y-%m-%d")
        
        try:
            # get the role of the user
            role = get_user_role(request.user)
            daily_performance = get_daily_performance(role, tin, material_type, start_date, end_date, plate_no, _status)
            # Initialize result structure
            result = {
                "individuals": [],
                "total_heavy_weight": 0,
                "total_medium_weight": 0,
                "total_light_weight": 0,
                "total_net_weight": 0,
            }
            # Iterate through GRN records
            for grn in daily_performance:
                customer = PurchaseCustomer.objects.filter(TIN=grn.customer).first()  # Find customer by TIN
                
                # Build individual entry
                individual_entry = {
                    "plate_no": grn.plate_no,
                    "customer": {
                        "name": f"{customer.fname} {customer.lname}" if customer else "Unknown",
                        "tin": grn.customer,
                    },
                    "grn_no": grn.grn_no,
                    "material_type": grn.material_type,
                    "heavy_weight": Decimal(str(grn.heavy_grade)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "medium_weight": Decimal(str(grn.medium_grade)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "light_weight": Decimal(str(grn.light_grade)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "net_weight": Decimal(str(grn.net_weight)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    "weight_date": grn.first_date
                }

                # Append to individuals list
                result["individuals"].append(individual_entry)

                # Update total weights
                result["total_heavy_weight"] += Decimal(str(grn.heavy_grade)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) or 0
                result["total_medium_weight"] += Decimal(str(grn.medium_grade)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) or 0
                result["total_light_weight"] += Decimal(str(grn.light_grade)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) or 0
                result["total_net_weight"] += Decimal(str(grn.net_weight)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) or 0
            material_types = MaterialType.get_material_types()
            allowed_status = Status.get_status_by_role(role)
            return JsonResponse({"result": "success", "message": "GRNs are filtered successfully", "data": result, "material_types": material_types, "allowed_status": allowed_status}, status=status.HTTP_200_OK)
        except ValueError:
            return JsonResponse({"result": "error", "message": f"TIN {tin} is invalid", "material_types": material_types, "allowed_status": allowed_status}, status=status.HTTP_400_BAD_REQUEST)
        except StatusException as e:
            return JsonResponse({"result": "error", "message": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except DailyPerformanceException as e:
            return JsonResponse({"result": "error", "message": e.message, "data": e.data, "material_types": material_types, "allowed_status": allowed_status}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Error occurred while calculating daily purchase performance %s:", e)
            return JsonResponse({"result": "error", "message": "Error occurred while calculating daily purchase performance", "material_types": material_types, "allowed_status": allowed_status}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def search_record(request):
    """
    Search record based on some filter criteria ==> Record No, Plate No, TIN, Material Type, Weight Date(First Date), GRN No, Status
    """
    if request.method == "GET":
        search_query = request.query_params.get("search_query", "").strip().lower()

        try:
            role = get_user_role(request.user)
            # Base QuerySet
            grn_records = GRN.objects.all().order_by("-record_time")
            
            filter = Q()
            allowed_status = Status.get_status_by_role(role)
            if search_query:
                filter |= Q(record_no__icontains=search_query)
                filter |= Q(plate_no__icontains=search_query)
                filter |= Q(customer__icontains=search_query)
                filter |= Q(material_type__icontains=search_query)
                filter |= Q(first_date__icontains=search_query)
                filter |= Q(grn_no__icontains=search_query)
                filter |= Q(status__icontains=search_query) & Q(status__in=allowed_status)

            grn_records = grn_records.filter(filter)
            paginated_query = grn_pagination(request, grn_records)
            material_types = MaterialType.get_material_types()
            status_list = Status.get_status_by_role(role)
            return JsonResponse({"result": "success", "message": "GRNs search result is fetched successfully", "data": paginated_query.data, "material_types": material_types, "status_list": status_list}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error occurred while searching grn %s:", e)
            return JsonResponse({"result": "error", "message": "Error occurred while searching grn"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector"])])
def add_waste_deduction(request):
    """
    Add waste deducted amount in Kg
    """
    if request.method == "POST":
        record_no = request.POST.get("record_no").strip()
        waste = request.POST.get("waste", "0").strip()
        
        if not is_digit(record_no):
            return JsonResponse({"result": "error", "message": f"Record no {record_no} must be digits only"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_digit(waste):
            return JsonResponse({"result": "error", "message": f"Waste deduction {waste} must be whole numbers"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # get the grn record
            get_grn = get_object_or_404(GRN.objects, record_no=record_no)
            
            if float(waste) >= float(get_grn.net_weight):
                return JsonResponse({"result": "error", "message": f"Waste deduction amount {waste} must be less than net weight {get_grn.net_weight}"}, status=status.HTTP_400_BAD_REQUEST)
            
            #net_weight = get_grn.net_weight
            first_weight = float(get_grn.first_weight or 0)
            second_weight = float(get_grn.second_weight or 0)
            net_weight = first_weight - second_weight
            # get material type
            material_type = get_grn.material_type
            if material_type == MaterialType.SCRAP.value:
                type = get_grn.type
                grade_percentage = parse_scrap_grade(type)
                
                new_net_weight = float(net_weight) - float(waste)
                heavy_grade = new_net_weight if grade_percentage["H"] == 100 else (grade_percentage["H"] / 100) * new_net_weight
                medium_grade = new_net_weight if grade_percentage["M"] == 100 else (grade_percentage["M"] / 100) * new_net_weight
                light_grade = new_net_weight if grade_percentage["L"] == 100 else (grade_percentage["L"] / 100) * new_net_weight
                
                # calculate the new net price
                new_net_price = (heavy_grade * float(get_grn.heavy_rate)) + (medium_grade * float(get_grn.medium_rate)) + (light_grade * float(get_grn.light_rate))
                
                # save the new info
                get_grn.net_weight = new_net_weight
                get_grn.heavy_grade = heavy_grade
                get_grn.medium_grade = medium_grade
                get_grn.light_grade = light_grade
                get_grn.net_price = new_net_price
                get_grn.waste_deduction = waste
                get_grn.save()
            else:
                fixed_rate = get_grn.fixed_rate
                
                # calculate the new net weight and new net price
                new_net_weight = float(net_weight) - float(waste)
                new_net_price = new_net_weight * float(fixed_rate)
                
                # save the new info
                get_grn.net_weight = new_net_weight
                get_grn.net_price = new_net_price
                get_grn.waste_deduction = waste
                get_grn.save()
            return JsonResponse({"result": "success", "message": f"Waste deduction {waste} is added successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while adding deduction: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while adding deduction"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector"])])
def edit_waste_deduction(request):
    """
    Edit waste deducted amount in Kg
    """
    if request.method == "PATCH":
        record_no = request.POST.get("record_no").strip()
        waste = request.POST.get("waste", 0).strip()
        
        if not is_digit(record_no):
            return JsonResponse({"result": "error", "message": f"Record no {record_no} must be digits only"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_digit(waste):
            return JsonResponse({"result": "error", "message": f"Waste deduction {waste} must be whole numbers"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # get the grn record
            get_grn = get_object_or_404(GRN.objects, record_no=record_no)
            
            if float(waste) >= float(get_grn.net_weight):
                return JsonResponse({"result": "error", "message": f"Waste deduction amount {waste} must be less than net weight {get_grn.net_weight}"}, status=status.HTTP_400_BAD_REQUEST)
            
            net_weight = float(get_grn.first_weight) - float(get_grn.second_weight) # get the net_weight back to first phase (on upload time)
            # get material type
            material_type = get_grn.material_type
            if material_type == MaterialType.SCRAP.value:
                type = get_grn.type
                grade_percentage = parse_scrap_grade(type)
                
                new_net_weight = float(net_weight) - float(waste)
                heavy_grade = new_net_weight if grade_percentage["H"] == 100 else (grade_percentage["H"] / 100) * new_net_weight
                medium_grade = new_net_weight if grade_percentage["M"] == 100 else (grade_percentage["M"] / 100) * new_net_weight
                light_grade = new_net_weight if grade_percentage["L"] == 100 else (grade_percentage["L"] / 100) * new_net_weight
                
                # calculate the new net price
                new_net_price = (heavy_grade * float(get_grn.heavy_rate)) + (medium_grade * float(get_grn.medium_rate)) + (light_grade * float(get_grn.light_rate))
                
                # save the new info
                get_grn.net_weight = new_net_weight
                get_grn.heavy_grade = heavy_grade
                get_grn.medium_grade = medium_grade
                get_grn.light_grade = light_grade
                get_grn.net_price = new_net_price
                get_grn.waste_deduction = waste
                get_grn.save()
            else:
                fixed_rate = get_grn.fixed_rate
                
                # calculate the new net weight and new net price
                new_net_weight = float(net_weight) - float(waste)
                new_net_price = new_net_weight * float(fixed_rate)
                
                # save the new info
                get_grn.net_weight = new_net_weight
                get_grn.net_price = new_net_price
                get_grn.waste_deduction = waste
                get_grn.save()
            return JsonResponse({"result": "success", "message": f"Waste deduction {waste} is edited successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while editing deduction: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while editing deduction"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def initialize_grn_serial_number(request, initial_serial_number):
    """
    Initialize a new grn serial number
    """
    try:
        # First, get the current active last used serial number
        last_used_serial_num = GRNSerialNumber.objects.filter(status='active').first()
        if last_used_serial_num and int(initial_serial_number) < last_used_serial_num.last_used_number:
            return JsonResponse({"result": "error", "message": "Initial serial number is among used serial numbers"}, status=status.HTTP_400_BAD_REQUEST)

        new_initial_serial_number = GRNSerialNumber.objects.create(
            initial_number=int(initial_serial_number),
        )
        new_initial_serial_number.save()
        GRNSerialNumber.objects.exclude(_id=new_initial_serial_number._id).update(status='expired')

        return JsonResponse({"result": "success", "message": "New initial GRN Serial Number is set.", "data": GRNSerialNumberSerializer(new_initial_serial_number).data}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while initializing new GRN Serial Number: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while initializing new GRN Serial Number", "content": e}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_grn_serial_numbers(request):
    """
    Get GRN Serial numbers
    """
    try:
        numbers = GRNSerialNumber.objects.all()
        serializer = GRNSerialNumberSerializer(numbers, many=True)
        return JsonResponse({"result": "success", "message": "GRN Serial Numbers", "content": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while getting GRN Serial Numbers: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while getting GRN Serial Numbers", "content": e}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def delete_grn_serial_number(request, num_id):
    """
    Delete GRN Serial Number
    """
    try:
        serial_number = get_object_or_404(GRNSerialNumber.objects, _id=num_id)
        serial_number.delete()
        return JsonResponse({"result": "success", "message": "You've deleted GRN Serial number successfully."}, status=status.HTTP_200_OK)
    except Http404:
        return JsonResponse({"result": "error", "message": "GRN serial number record not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Error occurred while deleting GRN Serial Number: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while deleting GRN Serial Number", "content": e}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_scrap_receipt(request, record_no):
    try:
        # Get GRN record
        grn_record = get_object_or_404(GRN.objects, record_no=record_no)
        serializer = GRNCustomerSerializer(grn_record)
        return JsonResponse({"result": "success", "message": record_no + " receipt is generated successfully.", "content": serializer.data}, status=status.HTTP_200_OK)

    except Http404:
        logger.error("No record found under given record no: %s", record_no)
        return JsonResponse({"result": "error", "message": "No record found under given record no."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Error occurred while getting GRN record: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while getting GRN record", "content": e}, status=status.HTTP_400_BAD_REQUEST)