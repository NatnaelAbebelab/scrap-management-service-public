from rest_framework import serializers

from grn.models import GRN
from .models import PurchaseCustomer

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseCustomer
        fields = '__all__'  # Include all fields

class PurchaseCustomerCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = PurchaseCustomer
        fields = [
            "first_name",
            "last_name",
            "phone",
            "email",
            "TIN",
            "business_name",
        ]

    # -------------------------
    # VALIDATIONS
    # -------------------------

    def validate_TIN(self, value):
        if PurchaseCustomer.objects.filter(TIN=value).exists():
            raise serializers.ValidationError("TIN already exists")
        return value

    def validate_business_name(self, value):
        if PurchaseCustomer.objects.filter(
            business_name__iexact=value
        ).exists():
            raise serializers.ValidationError("Business name already exists")
        return value.lower()

    def validate_email(self, value):
        return value.lower()

    # -------------------------
    # CREATE METHOD
    # -------------------------

    def create(self, validated_data):
        request = self.context.get("request")

        customer = PurchaseCustomer.objects.create(
            **validated_data,
            created_by=request.user,
            updated_by=request.user,
        )
        grns = GRN.objects.filter(customer=customer.TIN)
        total_net_price = sum(float(grn.net_price or 0) for grn in grns)

        customer.remaining_amount = total_net_price
        customer.save()

        return customer

class PurchaseCustomerUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = PurchaseCustomer
        fields = [
            "first_name",
            "last_name",
            "phone",
            "email",
            "TIN",
            "business_name",
        ]
        extra_kwargs = {
            "first_name": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
            "phone": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True},
            "TIN": {"required": False, "allow_blank": True},
            "business_name": {"required": False, "allow_blank": True},
        }

    # -------------------------
    # VALIDATIONS
    # -------------------------

    def validate_TIN(self, value):
        instance = self.instance
        if value and PurchaseCustomer.objects.filter(TIN=value).exclude(_id=instance._id).exists():
            raise serializers.ValidationError("TIN is already used")
        return value

    def validate_business_name(self, value):
        instance = self.instance
        if value and PurchaseCustomer.objects.filter(
            business_name__iexact=value
        ).exclude(_id=instance._id).exists():
            raise serializers.ValidationError("Business name is already used")
        return value.lower()

    def validate_email(self, value):
        return value.lower()

    # -------------------------
    # UPDATE METHOD
    # -------------------------

    def update(self, instance, validated_data):
        request = self.context.get("request")

        for attr, value in validated_data.items():
            if value != "":
                setattr(instance, attr, value)

        instance.updated_by = request.user
        instance.save()

        return instance

class GRNSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRN
        fields = '__all__'

class CustomerPaymentSerializer(serializers.Serializer):
    tin = serializers.CharField()
    record_nos = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False
    )

class PurchaseCustomerReportFilterSerializer(serializers.Serializer):
    tin = serializers.CharField(required=False, allow_blank=True)
    export = serializers.BooleanField(required=False, default=False)

class CustomerNetPaySummaryRequestSerializer(serializers.Serializer):
    tin = serializers.CharField(required=True)
    record_no = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False
    )

    def validate_record_no(self, value):
        for r in value:
            if not r.isdigit():
                raise serializers.ValidationError(
                    f"Record number {r} must be digits only"
                )
        return value

class CustomerInfoSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    business_name = serializers.CharField()
    tin = serializers.CharField()

class GRNSummarySerializer(serializers.Serializer):
    record_no = serializers.CharField()
    grn_no = serializers.CharField()
    serial_no = serializers.IntegerField()

    first_date = serializers.CharField()
    first_weight = serializers.CharField()

    heavy_grade = serializers.CharField()
    medium_grade = serializers.CharField()
    light_grade = serializers.CharField()

    heavy_rate = serializers.CharField()
    medium_rate = serializers.CharField()
    light_rate = serializers.CharField()

    net_price = serializers.CharField()

class CalculatedPriceSerializer(serializers.Serializer):
    sub_total = serializers.DecimalField(max_digits=20, decimal_places=2)
    vat_price = serializers.DecimalField(max_digits=20, decimal_places=2)
    grand_total = serializers.DecimalField(max_digits=20, decimal_places=2)
    with_holding_price = serializers.DecimalField(max_digits=20, decimal_places=2)
    net_pay = serializers.DecimalField(max_digits=20, decimal_places=2)

class CustomerNetPaySummarySerializer(serializers.Serializer):
    customer_info = CustomerInfoSerializer()
    grn = GRNSummarySerializer(many=True)
    calculated_price = CalculatedPriceSerializer()
