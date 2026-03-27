from datetime import datetime

from rest_framework import serializers

from grn.models import GRN
from helperFunctions.material_type import is_valid_material
from helperFunctions.validations import clean_tin


class GRNPlainReportFilterSerializer(serializers.Serializer):
    tin = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)
    material_type = serializers.CharField(required=False, allow_blank=True)
    plate_no = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.CharField(required=False, allow_blank=True)
    end_date = serializers.CharField(required=False, allow_blank=True)
    export = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError({
                    "start_date": "start_date must be less than or equal to end_date."
                })

        return attrs

class GRNAggregateReportFilterSerializer(serializers.Serializer):
    tin = serializers.CharField(required=False, allow_blank=True)
    material_type = serializers.CharField(required=False, allow_blank=True)
    plate_no = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    status = serializers.CharField(required=False, allow_blank=True)

    period = serializers.ChoiceField(
        choices=["daily", "weekly", "monthly", "quarterly", "yearly"],
        default="daily"
    )

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")

        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError({
                    "start_date": "start_date must be less than or equal to end_date."
                })

        return attrs

class GRNAggregateSerializer(serializers.ModelSerializer):
    class Meta:
        model = GRN
        fields = "__all__"

class GRNAggregateResponseSerializer(serializers.Serializer):
    data = serializers.ListField()
    totals = serializers.DictField()

class GeneralMetricsResponseSerializer(serializers.Serializer):
    weekly_purchase = serializers.IntegerField()
    total_vendors = serializers.IntegerField()
    total_grn = serializers.IntegerField()
    total_approved_grn = serializers.IntegerField()
    total_paid_grn = serializers.IntegerField()
    total_paid_amount = serializers.DecimalField(max_digits=18, decimal_places=2)

    # formatted text
    weekly_purchase_text = serializers.CharField()
    total_vendors_text = serializers.CharField()
    total_grn_text = serializers.CharField()
    total_approved_grn_text = serializers.CharField()
    total_paid_grn_text = serializers.CharField()
    total_paid_amount_text = serializers.CharField()

class ScrapGradePercentageResponseSerializer(serializers.Serializer):
    H = serializers.DecimalField(max_digits=10, decimal_places=2)
    M = serializers.DecimalField(max_digits=10, decimal_places=2)
    L = serializers.DecimalField(max_digits=10, decimal_places=2)

class YearlyPurchaseItemSerializer(serializers.Serializer):
    month = serializers.CharField()
    year = serializers.IntegerField()
    total_net_price = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_net_weight = serializers.DecimalField(max_digits=18, decimal_places=2)
    format_total_net_price = serializers.CharField()
    format_net_weight = serializers.CharField()

class YearlyPurchaseReportResponseSerializer(serializers.Serializer):
    data = YearlyPurchaseItemSerializer(many=True)

class InternalProcessReportSerializer(serializers.Serializer):
    tin = serializers.CharField(required=False, allow_null=True)
    material_type = serializers.CharField(required=False, allow_null=True)
    plate_no = serializers.CharField(required=False, allow_null=True)
    start_date = serializers.CharField(required=False, allow_null=True)
    end_date = serializers.CharField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_null=True)
    period = serializers.ChoiceField(
        choices=["daily", "weekly", "monthly", "yearly"],
        default="daily",
        allow_null=True
    )

    def validate_tin(self, value):
        if value in [None, ""]:
            return None

        cleaned = clean_tin(value)
        if not cleaned:
            raise serializers.ValidationError("Invalid TIN")

        return cleaned

    def validate_material_type(self, value):
        if value in [None, ""]:
            return None

        value = value.strip().lower()

        if not is_valid_material(value):
            raise serializers.ValidationError("Invalid material type")

        return value

    def validate(self, data):
        def parse_date(date):
            if not date:
                return None
            return datetime.strptime(date, "%Y-%m-%d").date()

        data["start_date"] = parse_date(data.get("start_date"))
        data["end_date"] = parse_date(data.get("end_date"))
        data["status"] = (data.get("status") or "").lower()

        return data