from rest_framework import serializers
from django.db.models import Q
from stock.models import StockBalance
from .models import GRN
from customer.models import Customer
from rate.models import Rate
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
class GRNSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRN
        fields = '__all__'  # Include all fields
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
    customer_fname = serializers.SerializerMethodField()
    customer_lname = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = GRN
        fields = [f.name for f in GRN._meta.fields] + [
            'customer_business_name',
            'customer_fname',
            'customer_lname',
            'amount'
        ]

    def get_customer_business_name(self, obj):
        customer = Customer.objects.filter(TIN=obj.customer.strip()).first()
        return customer.business_name if customer else None

    def get_customer_fname(self, obj):
        customer = Customer.objects.filter(TIN=obj.customer.strip()).first()
        return customer.fname if customer else None

    def get_customer_lname(self, obj):
        customer = Customer.objects.filter(TIN=obj.customer.strip()).first()
        return customer.lname if customer else None
    
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
    
