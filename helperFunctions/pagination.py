from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from collections import defaultdict
from rate.serializers import *
from grn.serializers import *
from internal.serializers import *
from user.serializers import *
from decimal import Decimal, ROUND_HALF_UP
import uuid
"""
These functions and classes are dedicated to work on query pagination
"""
class Pagination(PageNumberPagination):
    # /api/grn?page=2&page_size=20
    page_size = 10  # Number of items per page
    page_size_query_param = 'page_size'
    max_page_size = 100
class PaginationLimitOffset(LimitOffsetPagination):
    #/api/grn?limit=10&offset=10 → Next 10 results (skip first 10)
    default_limit = 10  # Default items per request
    max_limit = 100  # Maximum items a user can request
def grn_pagination_limit_offset(request, queryset):
    paginator = PaginationLimitOffset()
    paginated_queryset = paginator.paginate_queryset(queryset, request)
    serializer = GRNSerializer(paginated_queryset, many=True)
    return paginator.get_paginated_response(serializer.data)
def rate_pagination(request, queryset):
    paginator = Pagination()
    paginated_queryset = paginator.paginate_queryset(queryset, request)
    serializer = RateSerializer(paginated_queryset, many=True)
    return paginator.get_paginated_response(serializer.data)
def grn_pagination(request, queryset):
    paginator = Pagination()
    paginated_queryset = paginator.paginate_queryset(queryset, request)
    serializer = GRNCustomerSerializer(paginated_queryset, many=True)
    return paginator.get_paginated_response(serializer.data)
def scrap_move_pagination(request, queryset):
    paginator = Pagination()
    paginated_queryset = paginator.paginate_queryset(queryset, request)
    serializer = FactoryScrapMoveSerializer(paginated_queryset, many=True)
    return paginator.get_paginated_response(serializer.data)
def agency_pagination(request, queryset):
    paginator = Pagination()
    paginated_queryset = paginator.paginate_queryset(queryset, request)
    serializer = AgencySerializer(paginated_queryset, many=True)
    return paginator.get_paginated_response(serializer.data)
def agreement_pagination(request, queryset):
    paginator = Pagination()
    paginated_queryset = paginator.paginate_queryset(queryset, request)
    serializer = AgreementSerializer(paginated_queryset, many=True)
    return paginator.get_paginated_response(serializer.data)
def daily_scrap_move_pagination(request, queryset):
    paginator = Pagination()
    # paginated_queryset = paginator.paginate_queryset(queryset, request)
    serializer = DailyScrapMoveAggregateSerializer(queryset, many=True)
    paginated_queryset = paginator.paginate_queryset(serializer.data, request)
    # return paginator.get_paginated_response(paginated_queryset)
    return paginator.get_paginated_response(serializer.data)
def filter_daily_scrap_move_pagination(request, queryset, start_date, end_date):
    paginator = Pagination()
    # Prepare the result structure
    result = defaultdict(lambda: {
        "id": None,
        "business_name": None,
        "TIN": None,
        "material_type": None,
        "month": None,
        "total_weight": 0,
        "total_net_price": 0,
        "start_date": start_date,
        "end_date": end_date,
        "individuals": []
    })

    for record in queryset:     
        weight_date = datetime.strptime(record.weight_date, '%Y-%m-%d')
        month_year = weight_date.strftime('%Y-%m')

        # Fetch business name if TIN exists
        business_name = None
        agency = Agency.objects.filter(TIN=record.TIN).first()
        if agency:
            business_name = agency.business_name

        key = (record.TIN, record.material_type, month_year)
        group = result[key]

        group["id"] = uuid.uuid4()
        group["TIN"] = record.TIN
        group["business_name"] = business_name
        group["material_type"] = record.material_type
        group["month"] = month_year
        group["total_weight"] += Decimal(str(record.daily_net_weight)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) or 0
        group["total_net_price"] += Decimal(str(record.net_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) or 0
        
        group["individuals"].append({
            "record_id": record._id, 
            "daily_net_weight": Decimal(str(record.daily_net_weight)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            "net_price": Decimal(str(record.net_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            "rate": float(record.rate),
            "created_at": record.created_at,
            "weight_date": record.weight_date,
            "status": record.status
        })

    # Convert the result dictionary to a list
    result_list = list(result.values())
    paginated_queryset = paginator.paginate_queryset(result_list, request)
    serializer = DailyScrapMoveAggregateDictSerializer(paginated_queryset, many=True)
    
    return paginator.get_paginated_response(serializer.data)
def user_pagination(request, queryset):
    paginator = Pagination()
    paginated_queryset = paginator.paginate_queryset(queryset, request)
    serializer = UserSerializer(paginated_queryset, many=True)
    return paginator.get_paginated_response(serializer.data)