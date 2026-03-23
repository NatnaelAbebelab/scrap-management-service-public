from datetime import datetime

from django.utils import timezone
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
    requisition_no = serializers.CharField(
        max_length=50,
        validators=[
            UniqueValidator(
                queryset=MaterialRequisition.objects.all(),
                message="Requisition number already exists"
            )
        ]
    )
    items = MaterialRequisitionItemAddRequestSerializer(many=True)

    def validate_plant(self, value):
        if not MeltingPlants.objects.filter(_id=value).exists():
            raise serializers.ValidationError("Melting plant not found")
        return value

    def validate_requisition_date(self, value):
        today = timezone.now().date()

        if value > today:
            raise serializers.ValidationError(
                "Requisition date cannot be in the future"
            )

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
            "created_at",
            "updated_by",
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
    items = MaterialRequisitionItemUpdateRequestSerializer(many=True, allow_null=False, allow_empty=False)

    def validate_requisition_no(self, value):
        value = value.strip()

        if not value:
            return value

        requisition_id = self.initial_data.get("_id")

        exists = MaterialRequisition.objects.filter(
            requisition_no=value
        ).exclude(_id=requisition_id).exists()

        if exists:
            raise serializers.ValidationError("Requisition number already exists")

        return value

    def validate_requisition_date(self, value):
        today = timezone.now().date()

        if value > today:
            raise serializers.ValidationError(
                "Requisition date cannot be in the future"
            )

        return value

class ApprovedMaterialRequisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialRequisition
        fields = ['_id', 'requisition_no', 'requisition_date', 'total_requisition_quantity']

class RawMaterialIssueCreateSerializer(serializers.Serializer):
    material_requisition = serializers.UUIDField()
    issue_weight = serializers.FloatField()
    issue_date = serializers.DateField()
    issue_no = serializers.CharField(
        max_length=50,
        validators=[
            UniqueValidator(
                queryset=RawMaterialIssue.objects.all(),
                message="Issue number already exists"
            )
        ]
    )

    def validate_material_requisition(self, value):
        if not MaterialRequisition.objects.filter(_id=value).exists():
            raise serializers.ValidationError("Material requisition not found")
        return value

    def validate_issue_weight(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Issue weight must be greater than zero"
            )
        return value

    def validate(self, data):
        requisition_id = data.get("material_requisition")
        issue_date = data.get("issue_date")
        today = timezone.now().date()

        if requisition_id and issue_date:
            requisition = MaterialRequisition.objects.filter(_id=requisition_id).first()

            requisition_date = requisition.requisition_date

            if isinstance(requisition_date, str):
                requisition_date = datetime.strptime(requisition_date, "%Y-%m-%d").date()

            if issue_date < requisition_date:
                raise serializers.ValidationError(
                    {"issue_date": "Issue date must be greater than or equal to requisition date"}
                )

        if issue_date > today:
            raise serializers.ValidationError(
                "Issue date cannot be in the future"
            )

        return data

class RawMaterialIssueSerializer(serializers.ModelSerializer):
    material_requisition = serializers.PrimaryKeyRelatedField(
        queryset=MaterialRequisition.objects.all(),
        write_only=True
    )

    melting_plant = serializers.PrimaryKeyRelatedField(
        queryset=MeltingPlants.objects.all(),
        write_only=True
    )

    # Read full objects
    material_requisition_detail = MaterialRequisitionSerializer(
        source="material_requisition",
        read_only=True
    )

    melting_plant_detail = MeltingPlantsSerializer(
        source="melting_plant",
        read_only=True
    )

    class Meta:
        model = RawMaterialIssue
        fields = [
            "_id",

            "material_requisition",
            "melting_plant",

            # Read objects
            "material_requisition_detail",
            "melting_plant_detail",

            "issue_date",
            "issue_no",
            "issue_status",
            "issue_weight",

            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
            "is_deleted",
        ]

class RawMaterialIssueFilterSerializer(serializers.Serializer):
    requisition_no = serializers.CharField(required=False, allow_blank=True)
    issue_no = serializers.CharField(required=False, allow_blank=True)
    issue_status = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, data):
        start = data.get("start_date")
        end = data.get("end_date")

        if start and end and start > end:
            raise serializers.ValidationError(
                "start_date cannot be greater than end_date"
            )

        return data

class RawMaterialIssueEditSerializer(serializers.Serializer):
    _id = serializers.UUIDField()
    material_requisition = serializers.UUIDField(required=False, allow_null=True)
    issue_date = serializers.DateField(required=False, format="%Y-%m-%d")
    issue_no = serializers.CharField(max_length=255, required=False, allow_blank=True)
    issue_weight = serializers.FloatField(required=False)

    def validate_issue_no(self, value):
        """
        Ensure issue_no is unique unless it belongs to the same _id
        """
        issue_id = self.initial_data.get("_id")
        if RawMaterialIssue.objects.filter(issue_no=value).exclude(_id=issue_id).exists():
            raise serializers.ValidationError("Issue number already exists")
        return value

    def validate_issue_date(self, value):
        """
        Ensure issue_date >= requisition_date
        """
        today = timezone.now().date()
        requisition_id = self.initial_data.get("material_requisition")
        if requisition_id:
            requisition = MaterialRequisition.objects.filter(_id=requisition_id).first()
            requisition_date = requisition.requisition_date

            if isinstance(requisition_date, str):
                requisition_date = datetime.strptime(requisition_date, "%Y-%m-%d").date()

            if value < requisition_date:
                raise serializers.ValidationError(
                    {"issue_date": "Issue date must be greater than or equal to requisition date"}
                )

        if value > today:
            raise serializers.ValidationError(
                "Issue date cannot be in the future"
            )

        return value

    def validate_issue_weight(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Issue weight must be greater than zero")
        return value

class MaterialRequisitionReportSerializer(serializers.Serializer):

    requisition_no = serializers.CharField(required=False, allow_blank=True)

    requisition_start_date = serializers.DateField(required=False)
    requisition_end_date = serializers.DateField(required=False)

    melting_plant = serializers.UUIDField(required=False)

    min_quantity = serializers.FloatField(required=False)
    max_quantity = serializers.FloatField(required=False)

    status = serializers.CharField(required=False, allow_blank=True)

    export = serializers.BooleanField(required=False, default=False)

    def validate(self, data):
        start_date = data.get("requisition_start_date")
        end_date = data.get("requisition_end_date")

        min_qty = data.get("min_quantity")
        max_qty = data.get("max_quantity")

        # Validate date range
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError(
                    {"requisition_end_date": "End date must be greater than start date"}
                )

        # Validate quantity range
        if min_qty is not None and max_qty is not None:
            if min_qty > max_qty:
                raise serializers.ValidationError(
                    {"max_quantity": "max_quantity must be greater than min_quantity"}
                )

        return data

class RawMaterialIssueReportSerializer(serializers.Serializer):

    issue_no = serializers.CharField(required=False, allow_blank=True)

    issue_start_date = serializers.DateField(required=False)
    issue_end_date = serializers.DateField(required=False)

    issue_status = serializers.CharField(required=False, allow_blank=True)

    melting_plant = serializers.UUIDField(required=False)

    min_weight = serializers.FloatField(required=False)
    max_weight = serializers.FloatField(required=False)

    export = serializers.BooleanField(required=False, default=False)

    def validate(self, data):

        start_date = data.get("issue_start_date")
        end_date = data.get("issue_end_date")

        min_weight = data.get("min_weight")
        max_weight = data.get("max_weight")

        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                {"issue_end_date": "End date must be greater than start date"}
            )

        # Validate weight range
        if min_weight is not None and max_weight is not None:
            if min_weight > max_weight:
                raise serializers.ValidationError(
                    {"max_weight": "max_weight must be greater than min_weight"}
                )

        return data