from rest_framework import serializers
from .models import Agency, Agreement, AgreementRange, FactoryScrapMove, DailyScrapMoveAggregate
from decimal import Decimal, ROUND_HALF_UP
from helperFunctions.validations import clean_tin, is_valid_number, is_digit, is_valid_uuid
from helperFunctions.material_type import MaterialType, is_valid_material

class FactoryScrapUploadSerializer(serializers.Serializer):
    record_no = serializers.CharField()
    plate_no = serializers.CharField(required=False, allow_blank=True)
    first_weight = serializers.FloatField(required=False)
    first_date = serializers.CharField()
    first_time = serializers.CharField(required=False)
    second_weight = serializers.FloatField(required=False)
    second_date = serializers.CharField(required=False)
    second_time = serializers.CharField(required=False)
    net_weight = serializers.FloatField()
    firm = serializers.CharField()
    material = serializers.CharField()
    driver_name = serializers.CharField(required=False)

    def validate_firm(self, value):
        tin = clean_tin(value)

        if not is_valid_number(tin):
            raise serializers.ValidationError("Invalid TIN number")

        agency = Agency.objects.filter(TIN=tin).first()

        if not agency:
            raise serializers.ValidationError("TIN number is not registered")

        return tin

    def validate_material(self, value):

        material = value.strip().upper()

        if not is_valid_material(material.lower()):
            raise serializers.ValidationError("Invalid material type")

        return MaterialType[material].value

class FactoryScrapFilterSerializer(serializers.Serializer):
    tin = serializers.CharField(required=False)
    material_type = serializers.CharField(required=False)
    plate_no = serializers.CharField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    status = serializers.CharField(required=False)

    def validate_tin(self, value):
        if not clean_tin(value):
            raise serializers.ValidationError("TIN has no proper value")

        return clean_tin(value)

    def validate_material_type(self, value):
        if not is_valid_material(value.lower()):
            raise serializers.ValidationError("Material type is not valid")

        return value.lower()

    def validate(self, data):
        start = data.get("start_date")
        end = data.get("end_date")

        if start and end and start > end:
            raise serializers.ValidationError(
                "Start date must be before end date"
            )

        return data

class AgencyCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=255)
    last_name = serializers.CharField(max_length=255)
    tin = serializers.CharField(max_length=50)
    business_name = serializers.CharField(max_length=255)

    def validate(self, data):
        first_name = data.get("first_name").strip()
        last_name = data.get("last_name").strip()
        tin = data.get("tin").strip()
        business_name = data.get("business_name").strip()

        if not first_name or not last_name:
            raise serializers.ValidationError(
                "Agency officer name must be provided"
            )

        if not tin or not is_digit(tin):
            raise serializers.ValidationError(
                "TIN must contain only digits"
            )

        if not business_name:
            raise serializers.ValidationError(
                "Business name must be provided"
            )

        agency_tin = clean_tin(tin)

        if Agency.objects.filter(TIN=agency_tin).exists():
            raise serializers.ValidationError(f"TIN {tin} is already registered")

        data["TIN"] = agency_tin

        return data

class AgencyUpdateSerializer(serializers.Serializer):
    agency = serializers.UUIDField()
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    tin = serializers.CharField(required=False, allow_blank=True)
    business_name = serializers.CharField(required=False, allow_blank=True)
    agreement = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, data):

        agency_id = data.get("agency")
        tin = data.get("tin")
        business_name = data.get("business_name")

        agency = Agency.objects.filter(_id=agency_id).first()

        if not agency:
            raise serializers.ValidationError("Agency doesn't exist")

        if tin:
            if not is_digit(tin):
                raise serializers.ValidationError(f"TIN {tin} must be digits")

            if Agency.objects.filter(Q(TIN=tin) & ~Q(_id=agency_id)).exists():
                raise serializers.ValidationError(f"TIN {tin} is already used")

        if business_name:
            if Agency.objects.filter(
                Q(business_name__iexact=business_name) & ~Q(_id=agency_id)
            ).exists():
                raise serializers.ValidationError(
                    f"Business name '{business_name}' is already used"
                )

        data["agency_instance"] = agency

        return data

class AgencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = '__all__'  # Include all fields

class AgreementTierSerializer(serializers.Serializer):
    min_weight = serializers.FloatField(required=False, default=0)
    max_weight = serializers.CharField()
    rate = serializers.FloatField()

class AgreementCreateSerializer(serializers.Serializer):
    name = serializers.CharField()
    agency = serializers.UUIDField()
    material_type = serializers.CharField()

    agreement_proof = serializers.CharField()

    contract_details = serializers.DictField()

    agreements = AgreementTierSerializer(many=True)

    def validate_material_type(self, value):

        value = value.lower()

        if not is_valid_material(value):
            raise serializers.ValidationError("Material type is not valid")

        return value

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
        ranges = AgreementRange.objects.filter(agreement=str(obj._id))
        return AgreementRangeSerializer(ranges, many=True).data

class AgreementUpdateSerializer(serializers.Serializer):
    agreement = serializers.UUIDField()
    agency = serializers.UUIDField()
    tin = serializers.CharField()
    material_type = serializers.CharField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_null=True)
    agreement_proof = serializers.CharField(required=False, allow_null=True)

    contract_details = serializers.DictField(required=False)

    def validate_material_type(self, value):
        if not value:
            return None

        value = value.lower()

        if not is_valid_material(value):
            raise serializers.ValidationError("Material type is not valid")

        return value

    def validate_status(self, value):
        if not value:
            return None

        value = value.lower()

        if not is_valid_status(value):
            raise serializers.ValidationError("Agreement status is not valid")

        return value

class AgreementRangeUpdateItemSerializer(serializers.Serializer):
    _id = serializers.UUIDField()
    min_weight = serializers.FloatField(required=False)
    max_weight = serializers.FloatField(required=False)
    rate = serializers.FloatField(required=False)

class AgreementRangeUpdateSerializer(serializers.Serializer):
    agreement = serializers.UUIDField()
    ranges = serializers.DictField(
        child=AgreementRangeUpdateItemSerializer()
    )

class FactoryScrapMoveSerializer(serializers.ModelSerializer):
    class Meta:
        model = FactoryScrapMove
        fields = '__all__'

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

class DailyScrapMoveFilterSerializer(serializers.Serializer):
    tin = serializers.CharField(required=False, allow_null=True)
    material_type = serializers.CharField(required=False, allow_null=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_null=True)
    export = serializers.BooleanField(required=False, default=False)

    def validate_tin(self, value):
        if not value:
            return None

        cleaned = clean_tin(value)
        if not cleaned:
            raise serializers.ValidationError("TIN has no proper value")

        return cleaned

    def validate_material_type(self, value):
        if not value:
            return None

        if not is_valid_material(value):
            raise serializers.ValidationError("Invalid material type")

        return value.lower()

class DailyPerformanceFilterSerializer(serializers.Serializer):
    tin = serializers.CharField(required=False, allow_blank=True)
    plate_no = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.CharField(required=False, allow_blank=True)
    end_date = serializers.CharField(required=False, allow_blank=True)

    def validate_tin(self, value):
        if value:
            if not clean_tin(value):
                raise serializers.ValidationError("TIN has no proper value")
            return clean_tin(value)
        return value

    def validate(self, data):
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        def parse_date(date):
            if not date:
                return None
            return (
                datetime.strptime(date, "%d.%m.%Y").date()
                if "." in date
                else datetime.strptime(date, "%Y-%m-%d").date()
            )

        data["start_date"] = parse_date(start_date)
        data["end_date"] = parse_date(end_date)

        return data

class ApproveDailyScrapMoveSerializer(serializers.Serializer):
    data = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        allow_empty=False
    )

    def validate_data(self, value):
        valid_ids = [uid for uid in value if is_valid_uuid(uid)]

        if not valid_ids:
            raise serializers.ValidationError("No valid UUIDs provided")

        return valid_ids

class ApproveFactoryManagerSerializer(serializers.Serializer):
    data = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        allow_empty=False
    )

    def validate_data(self, value):
        valid_ids = [uid for uid in value if is_valid_uuid(uid)]

        if not valid_ids:
            raise serializers.ValidationError("No valid UUIDs provided")

        return valid_ids

class PayAgencyFinanceSerializer(serializers.Serializer):
    data = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        allow_empty=False
    )

    def validate_data(self, value):
        valid_ids = [uid for uid in value if is_valid_uuid(uid)]

        if not valid_ids:
            raise serializers.ValidationError("No valid UUIDs provided")

        return valid_ids

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