from rest_framework import serializers
from django.db.models import Q

from helperFunctions.roles import get_user_role
from helperFunctions.validations import is_digit
from stock.models import StockBalance
from .models import GRN, GRNSerialNumber
from customer.models import PurchaseCustomer
from rate.models import Rate
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
class GRNSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRN
        fields = '__all__'  # Include all fields

class GRNFilterSerializer(serializers.Serializer):
    tin = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    material_type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    plate_no = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)

class GETGRNSSerializer(serializers.ModelSerializer) :
    used_rate = serializers.SerializerMethodField()
    class Meta:
        model = GRN
        fields = [field.name for field in GRN._meta.get_fields()] + ['used_rate']
    
    def get_used_rate(self, obj) :
        material_type = ''
        defined_material_type = ['scrap', 'staffa', 'rebar', 'coils', 'chemicale']
        for mt in defined_material_type :
            if mt in obj.material_type.lower() : 
                material_type = mt
                break
        created_date = datetime.strptime(obj.created_at, "%Y-%m-%d")
        rate = Rate.objects.filter(Q(material_type=material_type)).all()
        rate_info = {
            'H' : '0',
            'M' : '0',
            'L' : '0',
            'F' : '0'
        }
        if rate.count() > 0 :
            for r in rate :
                if (datetime.strptime(r.created_at, "%Y-%m-%d") <= created_date) :
                    if (r.status != 'active' and datetime.strptime(r.expired_date, "%Y-%m-%d") > created_date) :
                        match r.material_type :
                            case 'scrap' :
                                rate_info['H'] = r.heavy_rate
                                rate_info['M'] = r.medium_rate
                                rate_info['L'] = r.light_rate
                                rate_info['F'] = '-'
                                return rate_info
                            case 'staffa' | 'rebar' | 'coils' | 'chemicale' :
                                rate_info['H'] = '-'
                                rate_info['M'] = '-'
                                rate_info['L'] = '-'
                                rate_info['F'] = r.fixed_rate
                                return rate_info
                    match r.material_type :
                        case 'scrap' :
                            rate_info['H'] = r.heavy_rate
                            rate_info['M'] = r.medium_rate
                            rate_info['L'] = r.light_rate
                            rate_info['F'] = '-'
                            return rate_info
                        case 'staffa' | 'rebar' | 'coils' | 'chemicale' :
                            rate_info['H'] = '-'
                            rate_info['M'] = '-'
                            rate_info['L'] = '-'
                            rate_info['F'] = r.fixed_rate
                            return rate_info    
        return rate_info

class PlainGRNSerializer(serializers.ModelSerializer) :
    class Meta:
        model = GRN
        fields = ['customer', 'created_at', 'email']

class GRNCustomerSerializer(serializers.ModelSerializer):
    customer_business_name = serializers.SerializerMethodField()
    customer_first_name = serializers.SerializerMethodField()
    customer_last_name = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = GRN
        fields = [f.name for f in GRN._meta.fields] + [
            'customer_business_name',
            'customer_first_name',
            'customer_last_name',
            'amount'
        ]

    def get_customer_business_name(self, obj):
        customer = PurchaseCustomer.objects.filter(TIN=obj.customer.strip()).first()
        return customer.business_name if customer else None

    def get_customer_first_name(self, obj):
        customer = PurchaseCustomer.objects.filter(TIN=obj.customer.strip()).first()
        return customer.first_name if customer else None

    def get_customer_last_name(self, obj):
        customer = PurchaseCustomer.objects.filter(TIN=obj.customer.strip()).first()
        return customer.last_name if customer else None
    
    def get_amount(self, obj):
        net_price = float(obj.net_price)
        if not net_price :
            return 0
        if net_price >= 1_000_000:
            return f"{round(net_price / 1_000_000, 2)}M"
        elif net_price >= 1_000:
            return f"{round(net_price / 1_000, 2)}k"
        else:
            return str(round(net_price, 2))
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('heavy_grade') is not None:
            data['heavy_grade'] = Decimal(str(data['heavy_grade'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if data.get('medium_grade') is not None:
            data['medium_grade'] = Decimal(str(data['medium_grade'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if data.get('light_grade') is not None:
            data['light_grade'] = Decimal(str(data['light_grade'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if data.get('net_price') is not None:
            data['net_price'] = Decimal(str(data['net_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) 
        return data

class ChangeGRNStatusSerializer(serializers.Serializer):
    record_no = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )
    grn_no = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    grn_img = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    scale_img = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    approve_img = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    target_status = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_record_no(self, value):
        # ensure each record_no is digits only
        for n in value:
            if not is_digit(n):
                raise serializers.ValidationError(f"Record number must be digits only: {n}")

        # check existence in DB
        existing = GRN.objects.filter(record_no__in=value).values_list("record_no", flat=True)
        missing = list(set(value) - set(existing))
        if missing:
            raise serializers.ValidationError(f"Records not found: {missing}")
        return value

    def validate(self, data):
        request = self.context.get("request")
        role = get_user_role(request.user)

        # Role-based required fields
        if role == "purchaser" and not data.get("grn_no"):
            raise serializers.ValidationError("grn_no is required for purchaser")
        if role == "purchase_head" and not data.get("approve_img"):
            raise serializers.ValidationError("approve_img is required for purchase_head")
        return data

class StockBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockBalance
        fields = [
            '_id',
            'purchase_weight',
            'transport_weight',
            'net_weight',
            'weight_date',
            'is_deleted',
            'created_by',
            'created_at',
            'updated_by',
            'updated_at',
            'record_time',
        ]
        read_only_fields = ['_id', 'record_time']
    
class GRNSerialNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRNSerialNumber
        fields = [
            '_id',
            'initial_number',
            'last_used_number',
            'status',
        ]

class RollbackGRNSerializer(serializers.Serializer):
    record_nos = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        allow_empty=False,
        allow_null=False
    )