from rest_framework import serializers

from stock.models import StockBalance
from stock.type_enum import StockBalanceOn


class BeginningBalanceSerializer(serializers.Serializer):
    beginning_qty = serializers.FloatField(min_value=0)
    beginning_value = serializers.FloatField(min_value=0)

class StockBalanceFilterSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    type = serializers.ChoiceField(
        choices=[e.value for e in StockBalanceOn],
        required=False,
        allow_null=True
    )
class StockBalanceSerializer(serializers.ModelSerializer):
    transaction_type = serializers.ChoiceField(
        choices=[e.value for e in StockBalanceOn],
        required=True
    )

    class Meta:
        model = StockBalance
        fields = [
            "_id",
            "transaction_type",
            "grn_no",
            "record_no",
            "issue_no",
            "purchased_qty",
            "issued_qty",
            "average_rate",
            "purchased_value",
            "issue_value",
            "remaining_qty",
            "remaining_value",
            "weight_date",
            "record_time",
            "is_deleted",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]
        read_only_fields = [
            "_id",
            "record_time",
            "created_at",
            "updated_at"
        ]