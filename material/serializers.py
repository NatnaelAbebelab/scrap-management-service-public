from rest_framework import serializers

from material.models import MaterialRequisitionItem, MaterialRequisition, RawMaterialIssue, MeltingPlants

class MeltingPlantsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeltingPlants
        fields = [
            "_id",
            "plant_name",
        ]

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

class ApprovedMaterialRequisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialRequisition
        fields = ['_id', 'requisition_no', 'requisition_date', 'total_requisition_quantity']