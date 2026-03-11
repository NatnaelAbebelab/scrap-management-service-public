from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import MaterialRequisitionItem, MaterialRequisition, RawMaterialIssue, MeltingPlants

class MeltingPlantCreateSerializer(serializers.Serializer):
    plant = serializers.CharField(
        source="plant_name",
        max_length=255,
        validators=[
            UniqueValidator(
                queryset=MeltingPlants.objects.all(),
                message="Melting plant already exists"
            )
        ]
    )

    def validate_plant(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Plant name cannot be empty"
            )

        return value

class MeltingPlantsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeltingPlants
        fields = [
            "_id",
            "plant_name",
        ]

class MeltingPlantUpdateSerializer(serializers.Serializer):
    _id = serializers.UUIDField(required=True)
    new_name = serializers.CharField(
        source="plant_name",
        max_length=255,
        validators=[
            UniqueValidator(
                queryset=MeltingPlants.objects.all(),
                message="Melting plant already exists"
            )
        ],
        allow_null=False
    )

    def validate_new_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Plant name cannot be empty")
        return value

class MaterialRequisitionItemAddRequestSerializer(serializers.Serializer):
    item_code = serializers.CharField(max_length=50)
    item_name = serializers.CharField(max_length=255)
    quantity = serializers.FloatField(min_value=0.01)
    unit_price = serializers.FloatField(min_value=0.0)

class MaterialRequisitionCreateSerializer(serializers.Serializer):
    plant = serializers.UUIDField()
    requisition_date = serializers.DateField()
    requisition_no = serializers.CharField(max_length=50)
    items = MaterialRequisitionItemAddRequestSerializer(many=True)

    def validate_plant(self, value):
        if not MeltingPlants.objects.filter(_id=value).exists():
            raise serializers.ValidationError("Melting plant not found")
        return value

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("At least one item is required")
        return items

class MaterialRequisitionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialRequisitionItem
        fields = [
            "_id",
            "item_code",
            "item_name",
            "quantity",
            "unit_price",
            "total_price",
        ]

class MaterialRequisitionSerializer(serializers.ModelSerializer):
    items = MaterialRequisitionItemSerializer(many=True, read_only=True)
    melting_plant = MeltingPlantsSerializer(read_only=True)
    
    class Meta:
        model = MaterialRequisition
        fields = [
            "_id",
            "melting_plant",
            "requisition_date",
            "requisition_no",
            "total_requisition_quantity",
            "total_requisition_price",
            "requisition_status",
            "created_by",
            "created_by_id",
            "created_at",
            "updated_by",
            "updated_by_id",
            "updated_at",
            "items",
        ]

class MaterialRequisitionFilterSerializer(serializers.Serializer):
    plant = serializers.UUIDField(required=False, allow_null=True)
    start_date = serializers.DateField(required=False, allow_null=True, format="%Y-%m-%d")
    end_date = serializers.DateField(required=False, allow_null=True, format="%Y-%m-%d")
    requisition_no = serializers.CharField(required=False, max_length=255, allow_null=True)
    status = serializers.CharField(required=False, max_length=50, allow_null=True)

    def validate(self, data):
        start = data.get("start_date")
        end = data.get("end_date")
        if start and end and start > end:
            raise serializers.ValidationError("start_date cannot be after end_date")
        return data

class MaterialRequisitionItemUpdateRequestSerializer(serializers.Serializer):
    _id = serializers.UUIDField(required=False)  # for existing items
    item_code = serializers.CharField(max_length=255)
    item_name = serializers.CharField(max_length=255)
    quantity = serializers.FloatField()
    unit_price = serializers.FloatField()

class MaterialRequisitionEditSerializer(serializers.Serializer):
    _id = serializers.UUIDField()
    plant = serializers.UUIDField(required=False, allow_null=True)
    requisition_date = serializers.DateField(required=False, allow_null=True, format="%Y-%m-%d")
    requisition_no = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    items = MaterialRequisitionItemUpdateRequestSerializer(many=True)

class ApprovedMaterialRequisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialRequisition
        fields = ['_id', 'requisition_no', 'requisition_date', 'total_requisition_quantity']

class RawMaterialIssueSerializer(serializers.ModelSerializer):
    requisition_no = serializers.CharField(source='material_requisition.requisition_no', read_only=True)
    total_requisition_quantity = serializers.CharField(source='material_requisition.total_requisition_quantity', read_only=True)
    
    class Meta:
        model = RawMaterialIssue
        fields = [
            "_id",
            "material_requisition",
            "requisition_no",
            "issue_date",
            "issue_no",
            "issue_status",
            "issue_weight",
            "total_requisition_quantity",
            "created_by",
            "created_by_id",
            "created_at",
            "updated_by",
            "updated_by_id",
            "updated_at",
            "is_deleted",
        ]
