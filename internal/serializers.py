from rest_framework import serializers
from .models import Agency, Agreement, AgreementRange, FactoryScrapMove, DailyScrapMoveAggregate
from decimal import Decimal, ROUND_HALF_UP

class AgencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = '__all__'  # Include all fields
class AgreementRangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgreementRange
        fields = '__all__'

class AgreementSerializer(serializers.ModelSerializer):
    agreement_ranges = serializers.SerializerMethodField()

    class Meta:
        model = Agreement
        fields = '__all__'

    def get_agreement_ranges(self, obj):
        # Fetch AgreementRange objects where agreement field matches Agreement _id
        ranges = AgreementRange.objects.filter(agreement=str(obj._id))
        return AgreementRangeSerializer(ranges, many=True).data
class FactoryScrapMoveSerializer(serializers.ModelSerializer):
    class Meta:
        model = FactoryScrapMove
        fields = '__all__' # Include all fields
class DailyScrapMoveAggregateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyScrapMoveAggregate
        fields = '__all__' # Include all fields
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('daily_net_weight') is not None:
            data['daily_net_weight'] = Decimal(str(data['daily_net_weight'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if data.get('net_price') is not None:
            data['net_price'] = Decimal(str(data['net_price'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return data


class IndividualRecordSerializer(serializers.Serializer):
    record_id = serializers.UUIDField()
    daily_net_weight = serializers.FloatField()
    net_price = serializers.FloatField()
    rate = serializers.FloatField()
    created_at = serializers.CharField()
    weight_date = serializers.CharField()
    status = serializers.CharField()

class DailyScrapMoveAggregateDictSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    business_name = serializers.CharField()
    TIN = serializers.CharField()
    material_type = serializers.CharField()
    month = serializers.CharField()
    total_weight = serializers.FloatField()
    total_net_price = serializers.FloatField()
    start_date = serializers.CharField(allow_blank=True)
    end_date = serializers.CharField(allow_blank=True)
    individuals = IndividualRecordSerializer(many=True)