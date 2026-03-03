from rest_framework import serializers
from .models import Rate

class RateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rate
        fields = '__all__'  # Include all fields

class AddRateSerializer(serializers.Serializer):
    material_type = serializers.CharField()
    heavy_rate = serializers.CharField(allow_null=True, required=False)
    medium_rate = serializers.CharField(allow_null=True, required=False)
    light_rate = serializers.CharField(allow_null=True, required=False)
    fixed_rate = serializers.CharField(allow_null=True, required=False)

class RateFilterSerializer(serializers.Serializer):
    material_type = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False, allow_blank=True)
    expired_from = serializers.DateField(required=False)
    expired_to = serializers.DateField(required=False)
    created_from = serializers.DateField(required=False)
    created_to = serializers.DateField(required=False)