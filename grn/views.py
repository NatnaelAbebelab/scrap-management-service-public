import logging

import pandas as pd
from django.core.exceptions import ValidationError
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from helperFunctions.grade_type import *
from helperFunctions.material_type import *
from helperFunctions.pagination import *
from helperFunctions.roles import *
from helperFunctions.status import *
from helperFunctions.validations import *
from stock.models import StockBalance
from stock.services import add_purchase_stock_record
from utils.exceptions import *
from utils.permissions import role_required
from .models import GRN, GRNSerialNumber
from .service import increment_grn_serial_number, filter_grn_service, change_grn_status_service, \
    rollback_grn_status_service, pay_customer_service, filter_grn_report_service, generate_grn_periodic_report, \
    build_grn_search_queryset, apply_waste_deduction, initialize_grn_serial_number

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
            casted_first_date=ToDateTime("first_date")
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
            casted_first_date=ToDateTime("first_date")
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

        grn_bulk = []
        stock_records = []

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

                grn = GRN(
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
                    created_by=request.user,
                    updated_by=request.user
                )
                grn_bulk.append(grn)

                # -------------------------
                # Stock Record (per GRN)
                # -------------------------
                date_key = record.get("DATE1")

                if material_type == "scrap":
                    stock = add_purchase_stock_record(
                        date_str=date_key,
                        purchase_qty=net_weight,
                        purchase_value=net_price,
                        grn_no=serial_number,
                        record_no=record_no,
                        heavy_rate=used_rate["H"],
                        medium_rate=used_rate["M"],
                        light_rate=used_rate["L"],
                        user=request.user
                    )
                    stock_records.append(stock)

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

            except Exception as e:
                logger.error("Error processing record %s: %s", record.get("RECORD NO"), e)
                skipped_records["invalid_records_no"].append(record.get("RECORD NO"))
                continue

        # -------------------------
        # Bulk Insert GRNs and Customers
        # -------------------------
        if grn_bulk:
            GRN.objects.bulk_create(grn_bulk, batch_size=500)
        if stock_records:
            StockBalance.objects.bulk_create(stock_records, batch_size=500)
        if customer_cache:
            PurchaseCustomer.objects.bulk_update(customer_cache.values(), ["remaining_amount"])

        return JsonResponse({
            "result": "success",
            "message": "File uploaded successfully",
            "skipped_records": skipped_records,
            "total_grns": len(grn_bulk),
            "stock_records_created": len(stock_records),
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

        return JsonResponse({
            "result": "success",
            "data": paginated_grn.data,
            "totalRecordsCount": total_records_count,
            "approvedRecordsCount": approved_records_count,
            "paidRecordsCount": paid_records_count,
            "otherRecordsCount": other_records_count
        })

    except Exception as e:
        logger.error("Error fetching GRN: %s", e)
        return JsonResponse({"result": "error", "message": "Error fetching GRN"}, status=400)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def change_grn_status(request):
    """
    Unified GRN status change API:
    - Bulk or single record
    - Role-based status transitions
    - Role-based required file fields
    - File upload handled by service
    """

    serializer = ChangeGRNStatusSerializer(
        data=request.data,
        context={"request": request}
    )
    if not serializer.is_valid():
        return JsonResponse({"result": "error", "message": serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        role = get_user_role(request.user)

        result = change_grn_status_service(
            record_nos=serializer.validated_data["record_no"],
            role=role,
            user=request.user,
            data=serializer.validated_data
        )

        return JsonResponse({"result": "success", "message": "Status changed successfully", "data": result},
                            status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error changing GRN status: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while changing status"},
                        status=status.HTTP_400_BAD_REQUEST)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head"])])
def rollback_grn(request):
    """
    Roll back GRN status for allowed roles using serializer validation.
    """
    serializer = RollbackGRNSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(
            {"result": "error", "message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    record_nos = serializer.validated_data['record_nos']

    # Validate each record_no is digits
    valid_record_nos = [n for n in record_nos if is_digit(n)]
    if not valid_record_nos:
        return JsonResponse(
            {"result": "error", "message": "All record numbers must be digits"},
            status=status.HTTP_400_BAD_REQUEST
        )

    role = get_user_role(request.user)

    try:
        result = rollback_grn_status_service(valid_record_nos, role, request.user)
        return JsonResponse({"result": "success", "message": "Status rolled back successfully", "data": result},
                            status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Error occurred while rolling back GRN status: %s", e)
        return JsonResponse(
            {"result": "error", "message": "Error occurred while rolling back status"},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def delete_grn(request, _id):
    if not is_valid_uuid(_id):
        return JsonResponse({"result": "error", "message": "Not valid object ID"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        grn = get_object_or_404(GRN.objects, _id=_id)
        grn.delete()
        return JsonResponse({"result": "success", "message": f"Record is deleted successfully"}, status=status.HTTP_200_OK)

    except Http404:
        logger.error("Record not found for ID: %s", _id)
        return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Error occurred while deleting record: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while deleting record"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def restore_grn(request, _id) :
    if not is_valid_uuid(_id):
        return JsonResponse({"result": "error", "message": "Not valid object ID"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        grn = get_object_or_404(GRN.all_objects, _id=_id, is_deleted=True)
        grn.restore()
        return JsonResponse({"result": "success", "message": f"Record is restored successfully"}, status=status.HTTP_200_OK)

    except Http404:
        logger.error("Record not found for ID: %s", _id)
        return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Error occurred while restoring record: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while restoring record"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "finance"])])
def pay_customer(request):

    serializer = PayCustomerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    record_numbers = serializer.validated_data["record_no"]

    try:

        result = pay_customer_service(
            record_numbers,
            request.user
        )

        return JsonResponse(
            {
                "result": "success",
                "message": "Payment successful",
                "data": result
            },
            status=status.HTTP_200_OK
        )

    except ValueError as e:

        return JsonResponse(
            {"result": "error", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:

        logger.error("Payment error: %s", e)

        return JsonResponse(
            {"result": "error", "message": "Payment processing failed"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def grn_plain_report_filter(request):

    serializer = GRNReportFilterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:

        queryset = filter_grn_report_service(
            serializer.validated_data
        )

        paginated = grn_pagination(request, queryset)

        return JsonResponse(
            {
                "result": "success",
                "message": "GRNs filtered successfully",
                "data": paginated.data,
            },
            status=status.HTTP_200_OK,
        )

    except StatusException as e:

        return JsonResponse(
            {"result": "error", "message": e.message},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except FilterException as e:

        return JsonResponse(
            {
                "result": "error",
                "message": e.message,
                "data": e.data,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:

        logger.error("Error filtering GRN: %s", e)

        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while filtering GRN",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"])])
def grn_periodic_report(request):
    """
    Generate periodic GRN report
    """

    serializer = GRNPeriodicReportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:

        report = generate_grn_periodic_report(serializer.validated_data)

        return JsonResponse(
            {
                "result": "success",
                "message": "Report generated successfully",
                "meta": {
                    "start_date": report["start_date"],
                    "end_date": report["end_date"],
                    "period": report["period"],
                },
                "data": report["data"],
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:

        logger.error("Error generating GRN periodic report: %s", e)

        return JsonResponse(
            {
                "result": "error",
                "message": "Failed to generate report",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_record(request):
    """
    GET /api/grn/search/?search_query=5017
    Search GRN records using a keyword.
    Search fields:
    - Record No
    - Plate No
    - TIN
    - Material Type
    - Weight Date (First Date)
    - GRN No
    - Status
    """

    serializer = GRNSearchSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    try:
        role = get_user_role(request.user)
        search_query = serializer.validated_data.get("search_query")

        queryset = build_grn_search_queryset(search_query, role)

        paginated_query = grn_pagination(request, queryset)

        return JsonResponse(
            {
                "result": "success",
                "message": "GRNs search result fetched successfully",
                "data": paginated_query.data,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error("Error occurred while searching GRN: %s", str(e))

        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while searching GRN",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector"])])
def add_waste_deduction(request):

    serializer = WasteDeductionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    record_no = serializer.validated_data["record_no"]
    waste = serializer.validated_data["waste"]

    try:

        result = apply_waste_deduction(record_no, waste)

        serializer = GRNSerializer(result)

        return JsonResponse(
            {
                "result": "success",
                "message": f"Waste deduction {waste} added successfully",
                "data": serializer.data
            },
            status=status.HTTP_200_OK,
        )

    except Http404:

        logger.error("GRN record is not found")

        return JsonResponse(
            {
                "result": "error",
                "message": "GRN record is not found",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    except ValueError as e:

        return JsonResponse(
            {
                "result": "error",
                "message": str(e),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:

        logger.error("Error occurred while adding waste deduction: %s", str(e))

        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while adding deduction",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor"])])
def initialize_grn_serial(request):

    serializer = InitializeGRNSerialSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:

        new_serial = initialize_grn_serial_number(
            serializer.validated_data["initial_serial_number"]
        )

        return JsonResponse(
            {
                "result": "success",
                "message": "New initial GRN serial number set successfully",
                "data": GRNSerialNumberSerializer(new_serial).data,
            },
            status=status.HTTP_201_CREATED
        )

    except ValidationError as e:

        return JsonResponse(
            {"result": "error", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:

        logger.error("Error initializing GRN serial number: %s", str(e))

        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while initializing GRN serial number",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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
        return JsonResponse(
            {
                "result": "success",
                "message": "You've deleted GRN Serial number successfully."},
            status=status.HTTP_200_OK
        )

    except Http404:
        return JsonResponse({"result": "error", "message": "GRN serial number record not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Error occurred while deleting GRN Serial Number: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while deleting GRN Serial Number", "content": e}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_scrap_receipt(request, record_no):
    try:
        # Get GRN record
        grn_record = get_object_or_404(GRN.objects, record_no=record_no)
        serializer = GRNCustomerSerializer(grn_record)

        return JsonResponse({
            "result": "success",
            "message": record_no + " receipt is generated successfully.",
            "content": serializer.data
        }, status=status.HTTP_200_OK)

    except Http404:

        logger.error("No record found under given record no: %s", record_no)

        return JsonResponse(
            {"result": "error",
             "message": "No record found under given record no."
             },
            status=status.HTTP_404_NOT_FOUND
        )

    except Exception as e:
        logger.error("Error occurred while getting GRN record: %s", e)

        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while getting GRN record",
                "content": e
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_material_types(request):
    try:
        material_types = MaterialType.get_material_types()
        return JsonResponse(
            {
                "result": "success",
                "message": "Material types are fetched successfully",
                "data": material_types
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error("Error occurred while getting material types: %s", e)

        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while getting material types"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_status_list(request):
    try:
        status_list = Status.get_all_statuses()
        return JsonResponse(
            {
                "result": "success",
                "message": "Status list is fetched successfully",
                "data": status_list
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error("Error occurred while getting status list: %s", e)

        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while getting status list"
            },
            status=status.HTTP_400_BAD_REQUEST
        )