from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from utils.permissions import role_required
from utils.exceptions import *
from django.shortcuts import get_object_or_404, get_list_or_404
from django.http import JsonResponse, Http404
from django.utils import timezone
from django.db import IntegrityError
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Q, Count, Sum, FloatField, F
from django.db.models.functions import Cast, Round
from django.db.models.expressions import F
from .models import Agency, Agreement, AgreementRange, FactoryScrapMove, DailyScrapMoveAggregate
from helperFunctions.material_type import *
from helperFunctions.grade_type import *
from helperFunctions.validations import *
from helperFunctions.pagination import *
from helperFunctions.status import *
from helperFunctions.roles import *
import pandas as pd
import json, uuid, os, logging, sys

from internal.tasks import process_in_background

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
        first_date_as_date=ToDate(F("first_date"))  # Convert first_date to DateField
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
# upload win scale file
@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "weight_man", "purchaser"])])
def upload_execl_file(request):
    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        skipped_records = {
            "dropped_rows": [],
            "invalid_data": []
        }
        try:
            # Ensure the file is an Excel file
            if not csv_file.name.endswith(".xlsx"):
                return JsonResponse({"result": "error", "message": "Invalid file format. Please upload an Excel file"}, status=status.HTTP_400_BAD_REQUEST)
            
            df = pd.read_excel(csv_file, engine="openpyxl")
            
            # Required columns
            columns_to_check = ["RECORD NO", "MATERIAL", "FIRM", "NET", "DATE1"]
            rows_to_drop = df[df[columns_to_check].isna().any(axis=1)]
            for index, row in rows_to_drop.iterrows():
                empty_cols = row[columns_to_check].isna()[row[columns_to_check].isna()].index.tolist()
                skipped_records["dropped_rows"].append({
                    "row": index,
                    "column": empty_cols,
                    "case": f"Missing values in {empty_cols}"
                })
            df.dropna(subset=columns_to_check, inplace=True)
            data_list = df.to_dict(orient="records")
            # Process each record
            for record in data_list :
                if not str(record["RECORD NO"]).strip():
                    skipped_records["invalid_data"].append({
                        "record_no": record["RECORD NO"],
                        "column": 0,
                        "case": f"Record no is not given"
                    })
                    continue
                if not str(record["FIRM"]).strip() or not is_valid_number(str(record["FIRM"]).strip()):
                    skipped_records["invalid_data"].append({
                        "record_no": record["RECORD NO"],
                        "column": 10,
                        "case": f"Invalid TIN number under FIRM column"
                    })
                    continue
                if not str(record["MATERIAL"]).strip() or not is_valid_material(str(record["MATERIAL"]).lower()):
                    skipped_records["invalid_data"].append({
                        "record_no": record["RECORD NO"],
                        "column": 11,
                        "case": f"Invalid Material Type under MATERIAL column"
                    })
                    continue
                if not str(record["NET"]) or not is_valid_number(str(record["NET"])):
                    skipped_records["invalid_data"].append({
                        "record_no": record["RECORD NO"],
                        "column": 9,
                        "case": f"Invalid Net weight under NET column"
                    })
                    continue
                if not str(record["DATE1"]):
                    skipped_records["invalid_data"].append({
                        "record_no": record["RECORD NO"],
                        "column": 6,
                        "case": f"Invalid First weight date under DATE1 column"
                    })
                    continue
                try:
                    agency_TIN = clean_tin(str(record["FIRM"]).strip())
                    agency = Agency.objects.filter(TIN=agency_TIN).first()
                    if not agency :
                        skipped_records["invalid_data"].append({
                            "record_no": record["RECORD NO"],
                            "column": 10,
                            "case": f"TIN number is not registered"
                        })
                        continue
                    scrap = FactoryScrapMove(
                        record_no= record["RECORD NO"],
                        plate_no=record["PLATE NO"],
                        first_weight=record["1ST WEIGHING"],
                        first_date=record["DATE1"],
                        first_time=record["TIME1"],
                        second_weight=record["2ND WEIGHING"],
                        second_date=record["DATE2"],
                        second_time=record["TIME2"],
                        net_weight=record["NET"],
                        agency=agency_TIN,
                        type=record["MATERIAL"],
                        material_type=MaterialType[record["MATERIAL"].strip().upper()].value,
                        driver_name=record["Driver name "],
                        item_code="item_code",
                        created_by=request.user.username,
                        created_at=today,
                        updated_by=request.user.username,
                        updated_at=today
                    )
                    scrap.save()
                except IntegrityError :
                    skipped_records["invalid_data"].append({
                        "record_no": record["RECORD NO"],
                        "column": 0,
                        "case": f"Record no is not given"
                    })
                    continue
                except ValueError :
                    skipped_records["invalid_data"].append({
                        "record_no": record["RECORD NO"],
                        "column": 10,
                        "case": f"Invalid TIN number under FIRM column"
                    })
                    continue
            #process_in_background()
            # record action log
            return JsonResponse({
                "result" : "success",
                "message": "File uploaded successfully",
                "skipped_records" : skipped_records,
                "total_records" : FactoryScrapMove.objects.count()
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error occurred while uploading file: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while uploading file"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "weight_man", "purchaser", "inspector", "purchase_head", "supervisor", "factory_manager", "finance", "manager"])])
def get_factory_scrap_records(request):
    """
    Fetch Scrap move records based on role ====> status
    """
    try :
        role = get_user_role(request.user)
        allowed_status = Status.get_status_by_role(role)
        individual_records = FactoryScrapMove.objects.filter(status__in=allowed_status).order_by("-record_time")
        paginated_records = scrap_move_pagination(request, individual_records)
        # get known status
        status_list = Status.get_status_by_role(role)
        return JsonResponse({
            "result": "success",
            "data": paginated_records.data,
            "status_list": status_list
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Error occurred while fetching factory scrap move: %s", e)
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while fetching factory scrap move",
        }, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "purchaser", "inspector", "purchase_head", "supervisor", "factory_manager", "finance", "manager"])])
def filter_factory_scrap_records(request):
    """
    Filter factory scrap move records by ===> TIN, Material Type, Plate_no, Start date, End date, status
    """
    tin = request.query_params.get("tin", "").strip()
    material_type = request.query_params.get("material_type", "").strip().lower()
    plate_no = request.query_params.get("plate_no", "").strip()
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
    
    try :
        role = get_user_role(request.user)
        allowed_status = Status.get_status_by_role(role)
        
        if _status and _status not in allowed_status:
            raise StatusException(f"{status} is not belong to {role}")
    
        # Base QuerySet
        factory_records = FactoryScrapMove.objects.all().order_by("-record_time")
        
        # Filter by TIN (Check if tin exists in Agency model)
        if tin and clean_tin(tin):
            agency = Agency.objects.filter(TIN=tin).first()
            if agency:
                factory_records = factory_records.filter(agency=tin)
        
        # Filter by material type
        if material_type:
            factory_records = factory_records.filter(material_type__iexact=material_type)
            
        factory_records = factory_records.annotate(
            casted_first_date=ToDate("first_date")
        )
        if start_date:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            factory_records = factory_records.filter(casted_first_date__gte=start_date)
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            factory_records = factory_records.filter(casted_first_date__lte=end_date)      
        
        if plate_no:
            factory_records = factory_records.filter(plate_no__iexact=plate_no)
        
        # Filter by Status
        if _status:
            grn_records = grn_records.filter(status=_status)
        else:
            grn_records = grn_records.filter(status__in=allowed_status)
        
        paginated_records = scrap_move_pagination(request, factory_records)
        return JsonResponse({"result": "success", "message": "Factory scrap move are filtered successfully", "data": paginated_records.data}, status=status.HTTP_200_OK)
    except ValueError:
        return JsonResponse({"result": "error", "message": f"TIN {tin} is invalid"}, status=status.HTTP_400_BAD_REQUEST)
    except StatusException as e:
        return JsonResponse({"result": "error", "message": e.message}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Error occurred while filtering records: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while filtering records"}, status=status.HTTP_400_BAD_REQUEST) 
@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def add_agency(request):
    if request.method == "POST":
        fname = request.POST.get("fname", "").strip()
        lname = request.POST.get("lname", "").strip()
        tin = request.POST.get("tin", "").strip()
        business_name = request.POST.get("business_name", "").strip()
        
        if not fname or not lname:
            return JsonResponse({"result": "error", "message": "Agency officer name must be provided"}, status=status.HTTP_400_BAD_REQUEST)
        if not tin or not is_digit(tin):
            return JsonResponse({"result": "error", "message": "TIN must be digits"}, status=status.HTTP_400_BAD_REQUEST)
        if not business_name:
            return JsonResponse({"result": "error", "message": "Business name must be provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            agency_TIN = clean_tin(tin)
            agency = Agency.all_objects.filter(TIN=agency_TIN).first()
            if agency:
                return JsonResponse({"result": "error", "message": f"TIN {tin} is already registered"}, status=status.HTTP_400_BAD_REQUEST)
            agency = Agency(
                fname=fname,
                lname=lname,
                TIN=agency_TIN,
                business_name=business_name,
                created_by=request.user.username,
                created_at=today,
                updated_by=request.user.username,
                updated_at=today
            )
            agency.save()
            return JsonResponse({"result": "success", "message": "Agency is registered successfully"}, status=status.HTTP_200_OK)
        except ValueError :
            return JsonResponse({"result": "error", "message": f"TIN {tin} is not valid TIN"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Error occurred while registering agency: %s", e)
            return JsonResponse({"result": "error", "message": "An error occurred while registering agency"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "finance", "manager"])])
def get_agencies(request):
    """
    Fetch registered and not deleted agencies
    """
    try :
        agencies = Agency.objects.all().order_by("-record_time")
        paginated_records = agency_pagination(request, agencies)
        # get list of available material types
        material_types = MaterialType.get_material_types()
        return JsonResponse({
            "result": "success",
            "data": paginated_records.data,
            "material_types": material_types
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Error occurred while fetching agencies: %s", e)
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while fetching agencies",
        }, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def update_agency(request):
    if request.method == "PATCH":
        agency = request.POST.get("agency").strip()
        fname = request.POST.get("fname").strip()
        lname = request.POST.get("lname").strip()
        tin = request.POST.get("tin").strip()
        business_name = request.POST.get("business_name").strip()
        agreement = request.POST.get("agreement", "").strip()
        
        if agency and not is_valid_uuid(agency):
            return JsonResponse({"result": "error", "message": "Agency Identification ID is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        if tin and not is_digit(tin):
            return JsonResponse({"result": "error", "message": f"TIN {tin} must be digits"}, status=status.HTTP_400_BAD_REQUEST)
        if agreement and not is_valid_uuid(agreement):
            return JsonResponse({"result": "error", "message": f"Agreement {agreement} is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            agency = Agency.objects.filter(_id=agency)
            if agency.exists():
                if Agency.objects.filter(Q(TIN=tin) & ~Q(_id=agency)).exists():
                    return JsonResponse({"result": "error", "message": f"TIN {tin} is already used"}, status=status.HTTP_400_BAD_REQUEST)
                if Agency.objects.filter(Q(business_name__iexact=business_name) & ~Q(_id=agency)).exists():
                    return JsonResponse({"result": "error", "message": f"Business name '{business_name}' is already used"}, status=status.HTTP_400_BAD_REQUEST)
                for field, label in zip([fname, lname, tin, business_name, agreement], ["fname", "lname", "TIN", "business_name", "agreement"]):
                        if field:
                            agency.update(**{label: field, "updated_by": request.user.username, "updated_at": today, "record_time": timezone.now()})
            else:
                return JsonResponse({"result": "error", "message": "Agency doesn't exist"}, status=status.HTTP_400_BAD_REQUEST)
            return JsonResponse({"result": "success", "message": "Agency is updated successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("An error occurred while updating agency: %s", e)
            return JsonResponse({"result": "error", "message": "An error occurred while updating agency"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def delete_agency(request):
    """Delete an agency"""
    if request.method == "DELETE":
        agency_id = request.POST.get("agency").strip()
        if not agency_id:
            return JsonResponse({"result": "error", "message": "Agency ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        if is_valid_uuid(agency_id):
            return JsonResponse({"result": "error", "message": "Agency ID is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            agency = get_object_or_404(Agency, _id=agency_id)
            agency.delete()
            return JsonResponse({"result": "success", "message": "Agency is deleted successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Agency record not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while deleting agency: %s ", e)
            return JsonResponse({"result": "error", "message": "Error occurred while deleting agency"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def restore_agency(request) :
    if request.method == "PATCH":
        tin = request.POST.get("tin").strip()
        
        if not is_digit(tin):
            return JsonResponse({"result": "error", "message": f"TIN {tin} is must be digits"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            tin = clean_tin(tin)
            get_agency = get_object_or_404(Agency.all_objects, TIN=tin, is_deleted=True)
            get_agency.restore()
            return JsonResponse({"result": "success", "message": f"Agency({tin}) is restored successfully"}, status=status.HTTP_200_OK)
        except ValueError :
            return JsonResponse({"result": "error", "message": f"TIN {tin} is not valid TIN"}, status=status.HTTP_400_BAD_REQUEST)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while restoring agency: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while restoring agency"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def add_agreement(request):
    if request.method == "POST":
        json_data = request.POST.get("data")
        proof = request.FILES.get("proof")
        
        if not json_data:
            return JsonResponse({"result": "error", "message": "Agreement information is missed"}, status=status.HTTP_400_BAD_REQUEST)
        if not proof:
            return JsonResponse({"result": "error", "message": "Agreement proof is must be given"}, status=status.HTTP_400_BAD_REQUEST)
        
        data_dict = json.loads(json_data)
        agency_id = data_dict.get("agency").strip()
        material_type = data_dict.get("material_type").strip().lower()
        
        if not is_valid_uuid(agency_id):
            return JsonResponse({"result": "error", "message": "Agency ID is not valid ID"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_valid_material(material_type):
            return JsonResponse({"result": "error", "message": "Material type is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            agency = Agency.objects.filter(_id=agency_id).first()
            if not agency:
                return JsonResponse({"result": "error", "message": "Agency and TIN doesn't matched"}, status=status.HTTP_400_BAD_REQUEST)
            tin = agency.TIN
            agreement = Agreement.objects.filter((Q(TIN=tin) & Q(agency=agency_id)) & Q(material_type__iexact=material_type)).first()
            if agreement:
                return JsonResponse({"result": "error", "message": "Agency agreement under material type already exists"}, status=status.HTTP_400_BAD_REQUEST)
            
            # validation on the ranges
            for i, params in enumerate(data_dict.get("agreements", [])):
                if float(params.get("min_weight", 0)) != 0 and not is_valid_number(params.get("min_weight")):
                    return JsonResponse({"result": "error", "message": "Minimum weight is invalid value"}, status=status.HTTP_400_BAD_REQUEST)
                
                if params.get("max_weight") != "MAX_FLAG" and not is_valid_number(params.get("max_weight")):
                    return JsonResponse({"result": "error", "message": "Maximum weight is invalid value"}, status=status.HTTP_400_BAD_REQUEST)
                
                if params.get("max_weight") == "MAX_FLAG":
                    params["max_weight"] = MAX_FLOAT
                
                if float(params.get("min_weight", 0)) > float(params.get("max_weight")):
                    return JsonResponse({"result": "error", "message": "Minimum weight is greater than Maximum weight"}, status=status.HTTP_400_BAD_REQUEST)
                
                # Check if max_weight of current range equals min_weight of next range
                if i < len(data_dict.get("agreements", [])) - 1:  # Ensure there's a next range
                    next_params = data_dict["agreements"][i + 1]
                    current_max = float(params.get("max_weight"))
                    next_min = float(next_params.get("min_weight", 0))
                    if current_max != next_min:
                        return JsonResponse(
                            {"result": "error", "message": f"Max weight ({current_max}) of range {i+1} does not equal min weight ({next_min}) of range {i+2}"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
            
            file_name = str(uuid.uuid4())
            if proof:
                file_path = os.path.join(settings.MEDIA_ROOT, "internal-agreement-proof", file_name + "." + proof.name.split(".")[-1])
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'wb+') as destination:
                    for chunk in proof.chunks():
                        destination.write(chunk)
                file_name = file_name + "." + proof.name.split(".")[-1]
            # save the agreement without range
            save_agreement = Agreement(
                    agreement_name=data_dict.get("name").lower(),
                    agency=agency_id,
                    TIN = tin,
                    material_type = material_type,
                    effective_date = data_dict.get("contract_details", {}).get("effective_start_date"),
                    duration = data_dict.get("contract_details", {}).get("contract_duration_months"),
                    agreement_proof=file_name,
                    created_by=request.user.username,
                    created_at=today,
                    updated_by=request.user.username,
                    updated_at=today
                )
            save_agreement.save()
            # save agreement range and rate
            for params in data_dict.get("agreements", {}):
                agreement_range = AgreementRange(
                    agreement=save_agreement,
                    agency=agency_id,
                    min_weight = params.get("min_weight"),
                    max_weight = params.get("max_weight"),
                    rate =  params.get("rate"),
                    created_by=request.user.username,
                    created_at=today,
                    updated_by=request.user.username,
                    updated_at=today
                )
                agreement_range.save()
            return JsonResponse({"result": "success", "message": "Agreement is submitted successfully"}, status=status.HTTP_200_OK)
        except ValueError:
            return JsonResponse({"result": "error", "message": f"TIN {tin} is invalid"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("An error occurred while submitting agreement:%s", e)
            return JsonResponse({"result": "error", "message": "An error occurred while submitting agreement"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "finance", "manager"])])
def get_agreements(request):
    """
    Fetch agency agreements
    """
    try :
        agreements = Agreement.objects.all().order_by("-record_time")
        paginated_records = agreement_pagination(request, agreements)
        material_types = MaterialType.get_material_types()
        return JsonResponse({
            "result": "success",
            "data": paginated_records.data,
            "material_types": material_types
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error("Error occurred while fetching agreements: %s", e)
        return JsonResponse({
            "result": "error",
            "message": "Error occurred while fetching agreements",
        }, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def update_agreement(request):
    if request.method == "PATCH":
        json_data = request.POST.get("data")
        proof = request.FILES.get("proof")
        
        if not json_data:
            return JsonResponse({"result": "error", "message": "Agreement information is missed"}, status=status.HTTP_400_BAD_REQUEST)
        
        data_dict = json.loads(json_data)
        agreement_id = data_dict.get("agreement").strip()
        agency_id = data_dict.get("agency").strip()
        tin = data_dict.get("tin").strip()
        material_type = data_dict.get("material_type").strip().lower()
        _status = data_dict.get("status").strip().lower()
        
        if not is_valid_uuid(agreement_id):
            return JsonResponse({"result": "error", "message": "Agreement ID is not valid ID"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_valid_uuid(agency_id):
            return JsonResponse({"result": "error", "message": "Agency ID is not valid ID"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_valid_material(material_type):
            return JsonResponse({"result": "error", "message": "Material type is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        if not is_valid_status(_status):
            return JsonResponse({"result": "error", "message": "Agreement status is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            tin = clean_tin(tin)
            agreement = Agreement.objects.filter(_id=agreement_id)
            agency = Agency.objects.filter(Q(_id=agency_id) & Q(TIN=tin)).first()
            if not agreement.exists():
                return JsonResponse({"result": "error", "message": "Agreement doesn't exist"}, status=status.HTTP_400_BAD_REQUEST)
            if not agency:
                return JsonResponse({"result": "error", "message": f"Agency does not exist or TIN {tin} is mismatched"}, status=status.HTTP_400_BAD_REQUEST)

            if proof:
                file_name = str(uuid.uuid4())
                file_path = os.path.join(settings.MEDIA_ROOT, "internal-agreement-proof", file_name + "." + proof.name.split(".")[-1])
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'wb+') as destination:
                    for chunk in proof.chunks():
                        destination.write(chunk)
                agreement.agreement_proof = file_name + "." + proof.name.split(".")[-1]
            
            for field, label in zip([data_dict.get("name"), agency_id, tin, material_type, data_dict.get("contract_details").get("effective_start_date"),
                                    data_dict.get("contract_details").get("contract_duration_months"), Status.get_status(_status).status_value], 
                                    ["agreement_name", "agency", "TIN", "material_type", "effective_date", "duration", "status"]):
                if field:
                    agreement.update(**{label: field, "updated_by": request.user.username, "updated_at": today, "record_time": timezone.now()})       
            return JsonResponse({"result": "success", "message": "Agreement information is updated successfully"}, status=status.HTTP_200_OK)
        except ValueError:
            return JsonResponse({"result": "error", "message": f"TIN {tin} is invalid"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("An error occurred while updating the agreement information: %s", e)
            return JsonResponse({"result": "error", "message": "An error occurred while updating the agreement information"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def update_agreement_range(request):
    if request.method == "PATCH":
        json_data = request.POST.get("data")
        
        if not json_data:
            return JsonResponse({"result": "error", "message": "Agreement range information is missed"}, status=status.HTTP_400_BAD_REQUEST)
        
        data_dict = json.loads(json_data)
        agreement_id = data_dict.get("agreement").strip()
        ranges = data_dict.get("ranges", {})
        if not is_valid_uuid(agreement_id):
            return JsonResponse({"result": "error", "message": "Agreement ID is not valid ID"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if ranges:
                for key, value in ranges.items():   
                    if not is_valid_uuid(key):
                        return JsonResponse({"result": "error", "message": f"Range ID {key} is not valid"}, status=status.HTTP_400_BAD_REQUEST)
                    agreement_range = AgreementRange.objects.filter(Q(agreement=agreement_id) & Q(_id=key))
                    if not agreement_range.exists():
                        return JsonResponse({"result": "error", "message": f"Agreement range Id {key} is not found under agreement {agreement_id}"}, status=status.HTTP_400_BAD_REQUEST)
                    # Fields to update
                    fields = [value.get("min_weight"), value.get("max_weight"), value.get("rate")]
                    labels = ["min_weight", "max_weight", "rate"]
                    
                    # Dictionary for valid updates
                    update_data = {"updated_by": request.user.username, "updated_at": today, "record_time": timezone.now()}

                    for field, label in zip(fields, labels):
                        if field:  # Skip empty values
                            update_data[label] = field
                    # Perform update if there are valid fields
                    if update_data:
                        agreement_range.update(**update_data)
                return JsonResponse({"result": "success", "message": "Agreement range updated successfully"}, status=status.HTTP_200_OK)
            else:
                return JsonResponse({"result": "error", "message": "Agreement ranges is not provided"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("An error occurred while updating the agreement range: %s", e)
            return JsonResponse({"result": "error", "message": "An error occurred while updating the agreement range"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PUT'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def update_agreement_range_put(request):
    if request.method == "PUT":
        json_data = request.body
        
        if not json_data:
            return JsonResponse({"result": "error", "message": "Agreement range information is missed"}, status=status.HTTP_400_BAD_REQUEST)
        
        data_dict = json.loads(json_data)
        agreement_id = data_dict.get("agreement", "").strip()
        contract_details = data_dict.get("contract_details", {})
        material_type = data_dict.get("material_type", "").strip().lower()
        ranges = data_dict.get("ranges", {})
        
        if not is_valid_uuid(agreement_id):
            return JsonResponse({"result": "error", "message": "Agreement ID is not valid ID"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            agreement = Agreement.objects.filter(_id=agreement_id)
            if not agreement.exists():
                return JsonResponse({"result": "error", "message": "Agreement doesn't exist"},
                                    status=status.HTTP_400_BAD_REQUEST)

            update_fields = {}
            effective_date = contract_details.get("effective_start_date")
            duration = contract_details.get("contract_duration_months")

            if material_type:
                if not is_valid_material(material_type):
                    return JsonResponse({"result": "error", "message": "Material type is not valid"},
                                        status=status.HTTP_400_BAD_REQUEST)
                update_fields["material_type"] = material_type

            if effective_date:
                update_fields["effective_date"] = effective_date

            if duration:
                update_fields["duration"] = duration

            if update_fields:
                agreement.update(**update_fields,
                                 updated_by=request.user.username,
                                 updated_at=today,
                                 record_time=timezone.now())
            # Collect valid ranges for continuity check
            valid_ranges = []
            for key, value in ranges.items():
                if not value:
                    continue  # Skip empty entries

                if not is_valid_uuid(key):
                    continue  # Skip invalid UUIDs

                min_weight = value.get("min_weight")
                max_weight = value.get("max_weight")
                rate = value.get("rate")

                # Skip if any required field is missing
                if min_weight is None or max_weight is None or rate is None:
                    continue
                
                # Validation on individual range
                if float(min_weight) != 0 and not is_valid_number(min_weight):
                    return JsonResponse({"result": "error", "message": f"Minimum weight is invalid value for range {key}"}, status=status.HTTP_400_BAD_REQUEST)
                
                if max_weight != "MAX_FLAG" and not is_valid_number(max_weight):
                    return JsonResponse({"result": "error", "message": f"Maximum weight is invalid value for range {key}"}, status=status.HTTP_400_BAD_REQUEST)
                
                # Store max_weight for continuity check (before converting MAX_FLAG)
                effective_max_weight = MAX_FLOAT if max_weight == "MAX_FLAG" else max_weight
                
                if float(min_weight) > float(effective_max_weight):
                    return JsonResponse({"result": "error", "message": f"Minimum weight is greater than Maximum weight for range {key}"}, status=status.HTTP_400_BAD_REQUEST)
                
                # Store range for continuity check
                valid_ranges.append((key, {
                    "min_weight": min_weight,
                    "max_weight": effective_max_weight,
                    "rate": rate
                }))
            
            # Sort ranges by min_weight for continuity check
            sorted_ranges = sorted(valid_ranges, key=lambda x: float(x[1]["min_weight"]))
            
            # Check continuity: max_weight of current range == min_weight of next range
            for i, (range_id, params) in enumerate(sorted_ranges):
                if i < len(sorted_ranges) - 1:  # Skip for last range
                    current_max = float(params["max_weight"])
                    next_range_id, next_params = sorted_ranges[i + 1]
                    next_min = float(next_params["min_weight"])
                    if current_max != next_min:
                        return JsonResponse(
                            {"result": "error", "message": f"Max weight ({current_max}) of range {range_id} does not equal min weight ({next_min}) of range {next_range_id}"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
            
            # Proceed with database updates for valid ranges
            for key, params in valid_ranges:
                current_range = AgreementRange.objects.filter(Q(_id=key) & Q(agreement=agreement_id)).first()
                if current_range:
                    agency_id = current_range.agency
                    current_range.delete()
                    AgreementRange.objects.create(
                        #_id=key,
                        agreement=agreement_id,
                        agency=agency_id,
                        min_weight=params["min_weight"],
                        max_weight=params["max_weight"] if params["max_weight"] != MAX_FLOAT else "MAX_FLAG",
                        rate=params["rate"],
                        created_by=request.user.username,
                        created_at=today,
                        updated_by=request.user.username,
                        updated_at=today,
                        record_time=timezone.now()
                    )
            
            return JsonResponse({"result": "success", "message": "Agreement range updated successfully"}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error("An error occurred while updating the agreement range: %s", e)
            return JsonResponse({"result": "error", "message": "An error occurred while updating agreement range"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def delete_agreement(request):
    """Delete an agreement with respective range"""
    if request.method == "DELETE":
        agreement_id = request.POST.get("agreement").strip()
        if not agreement_id:
            return JsonResponse({"result": "error", "message": "Agreement ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        if is_valid_uuid(agreement_id):
            return JsonResponse({"result": "error", "message": "Agreement ID is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            agreement = get_object_or_404(Agreement, _id=agreement_id)
            agreement_range = get_list_or_404(AgreementRange, agreement=agreement_id)
            agreement_range.delete()
            agreement.delete()
            return JsonResponse({"result": "success", "message": "Agreement is deleted successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Delete operation failed: %s ", e)
            return JsonResponse({"result": "error", "message": "Delete operation failed"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "supervisor", "manager"])])
def restore_agreement(request) :
    if request.method == "PATCH":
        agreement_id = request.POST.get("agreement").strip()
        
        if not is_valid_uuid(agreement_id):
            return JsonResponse({"result": "error", "message": "Agreement ID is not valid"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            get_agreement = get_object_or_404(Agreement.all_objects, _id=agreement_id, is_deleted=True)
            get_agreement_range = get_list_or_404(AgreementRange.all_objects, agreement=agreement_id, is_deleted=True)
            get_agreement_range.restore()
            get_agreement.restore()
            return JsonResponse({"result": "success", "message": f"Agreement({agreement_id}) is restored successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while restoring agreement: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while restoring agreement"}, status=status.HTTP_400_BAD_REQUEST)
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