from rest_framework import serializers


class BeginningBalanceSerializer(serializers.Serializer):
    beginning_qty = serializers.FloatField(min_value=0)
    beginning_value = serializers.FloatField(min_value=0)