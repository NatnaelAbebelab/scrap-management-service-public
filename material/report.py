import uuid
from datetime import datetime
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from material.models import MaterialRequisition, RawMaterialIssue


@permission_classes([IsAuthenticated])
class MaterialRequisitionFilter:
    """
    Filter class for Material Requisition with the specified filters:
    1. Requisition_no
    2. Requisition_date_range
    3. Melting_plant
    4. Quantity_range
    5. Requisition_status
    """

    @staticmethod
    def apply_filters(queryset, filters):
        """
        Apply all specified filters to the MaterialRequisition queryset

        Args:
            queryset: Django queryset of MaterialRequisition
            filters: Dictionary containing filter parameters

        Returns:
            Filtered queryset
        """
        if not filters:
            return queryset

        # Always exclude deleted records unless explicitly requested
        if not filters.get('include_deleted', False):
            queryset = queryset.filter(is_deleted=False)

        # 1. Requisition Number Filter
        requisition_no = filters.get('requisition_no')
        if requisition_no:
            queryset = MaterialRequisitionFilter._apply_requisition_no_filter(
                queryset, requisition_no
            )

        # 2. Requisition Date Range Filter
        start_date = filters.get('requisition_start_date')
        end_date = filters.get('requisition_end_date')
        if start_date or end_date:
            queryset = MaterialRequisitionFilter._apply_date_range_filter(
                queryset, start_date, end_date
            )

        # 3. Melting Plant Filter
        melting_plant = filters.get('melting_plant')
        if melting_plant:
            queryset = MaterialRequisitionFilter._apply_melting_plant_filter(
                queryset, melting_plant
            )

        # 4. Quantity Range Filter
        min_quantity = filters.get('min_quantity')
        max_quantity = filters.get('max_quantity')
        if min_quantity is not None or max_quantity is not None:
            queryset = MaterialRequisitionFilter._apply_quantity_range_filter(
                queryset, min_quantity, max_quantity
            )

        # 5. Requisition Status Filter
        status = filters.get('requisition_status')
        if status:
            queryset = MaterialRequisitionFilter._apply_status_filter(
                queryset, status
            )

        return queryset

    @staticmethod
    def _apply_requisition_no_filter(queryset, requisition_no):
        if isinstance(requisition_no, str):
            requisition_no = requisition_no.strip()
            if requisition_no.isdigit():
                return queryset.filter(requisition_no__icontains=requisition_no)
        return queryset

    @staticmethod
    def _apply_date_range_filter(queryset, start_date, end_date):
        # Clean inputs
        if start_date:
            start_date = str(start_date).strip()

        if end_date:
            end_date = str(end_date).strip()

        # Build filters
        filters = {}

        if start_date:
            # Check if the date is a valid YYYY-MM-DD format
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                filters['requisition_date__gte'] = start_dt
            except:
                pass  # Skip invalid date

        if end_date:
            # Check if the date is a valid YYYY-MM-DD format
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                filters['requisition_date__lte'] = end_dt
            except:
                pass  # Skip invalid date

        if filters:
            return queryset.filter(**filters)

        return queryset

    @staticmethod
    def _apply_melting_plant_filter(queryset, melting_plant):
        if melting_plant:
            try:
                plant_id = str(melting_plant).strip()
                uuid.UUID(plant_id)
                return queryset.filter(melting_plant_id=plant_id)
            except (ValueError, TypeError, AttributeError):
                pass

        return queryset

    @staticmethod
    def _apply_quantity_range_filter(queryset, min_quantity, max_quantity):
        filters = {}

        if min_quantity:
            try:
                min_qty = float(min_quantity)
                filters['total_requisition_quantity__gte'] = min_qty
            except (ValueError, TypeError):
                pass

        if max_quantity:
            try:
                max_qty = float(max_quantity)
                filters['total_requisition_quantity__lte'] = max_qty
            except (ValueError, TypeError):
                pass

        if filters:
            return queryset.filter(**filters)

        return queryset

    @staticmethod
    def _apply_status_filter(queryset, status):
        if status:
            status = str(status).strip().lower()
            return queryset.filter(requisition_status=status)
        return queryset

    @staticmethod
    def get_filtered_queryset(base_queryset=None, **filters):
        """
        Convenience method to get filtered queryset

        Usage:
            qs = MaterialRequisitionFilter.get_filtered_queryset(
                requisition_no='MR001',
                requisition_start_date='2024-01-01',
                requisition_end_date='2024-01-31',
                melting_plant=uuid,
                min_quantity=50,
                max_quantity=200,
                requisition_status='APPROVED'
            )
        """
        if base_queryset is None:
            base_queryset = MaterialRequisition.objects.all()

        return MaterialRequisitionFilter.apply_filters(base_queryset, filters)


class RawMaterialIssueFilter:
    """
    Filter class for Raw Material Issue with specified filters:
    1. issue_no
    2. issue_date_range
    3. issue_status
    4. issue_weight_range
    """

    @staticmethod
    def apply_filters(queryset, filters):
        """
        Apply all specified filters to the RawMaterialIssue queryset

        Args:
            queryset: Django queryset of RawMaterialIssue
            filters: Dictionary containing filter parameters

        Returns:
            Filtered queryset
        """
        if not filters:
            return queryset

        # 1. Issue Number Filter
        issue_no = filters.get('issue_no')
        if issue_no:
            queryset = RawMaterialIssueFilter._apply_issue_no_filter(
                queryset, issue_no
            )

        # 2. Issue Date Range Filter
        start_date = filters.get('issue_start_date')
        end_date = filters.get('issue_end_date')
        if start_date or end_date:
            queryset = RawMaterialIssueFilter._apply_date_range_filter(
                queryset, start_date, end_date
            )

        # 3. Issue Status Filter
        issue_status = filters.get('issue_status')
        if issue_status:
            queryset = RawMaterialIssueFilter._apply_status_filter(
                queryset, issue_status
            )

        # 4. Issue Weight Range Filter
        min_weight = filters.get('min_weight')
        max_weight = filters.get('max_weight')
        if min_weight is not None or max_weight is not None:
            queryset = RawMaterialIssueFilter._apply_weight_range_filter(
                queryset, min_weight, max_weight
            )

        return queryset

    @staticmethod
    def _apply_issue_no_filter(queryset, issue_no):
        if issue_no & issue_no.isdigit():
            issue_no = str(issue_no).strip()
            return queryset.filter(issue_no__icontains=issue_no)
        return queryset

    @staticmethod
    def _apply_date_range_filter(queryset, start_date, end_date):
        # Clean date strings
        if start_date:
            start_date = str(start_date).strip()
        if end_date:
            end_date = str(end_date).strip()

        filters = {}

        if start_date:
            # Validate and apply start date
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                filters['issue_date__gte'] = start_dt
            except (ValueError, TypeError):
                pass

        if end_date:
            # Validate and apply end date
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                filters['issue_date__lte'] = end_dt
            except (ValueError, TypeError):
                pass

        if filters:
            return queryset.filter(**filters)

        return queryset

    @staticmethod
    def _apply_status_filter(queryset, issue_status):
        if issue_status:
            issue_status = str(issue_status).strip().lower()
            return queryset.filter(issue_status=issue_status)
        return queryset

    @staticmethod
    def _apply_weight_range_filter(queryset, min_weight, max_weight):
        filters = {}

        # Handle min weight
        if min_weight is not None:
            try:
                min_wt = float(min_weight)
                filters['issue_weight__gte'] = min_wt
            except (ValueError, TypeError):
                pass

        # Handle max weight
        if max_weight is not None:
            try:
                max_wt = float(max_weight)
                filters['issue_weight__lte'] = max_wt
            except (ValueError, TypeError):
                pass

        if filters:
            return queryset.filter(**filters)

        return queryset

    @staticmethod
    def get_filtered_queryset(base_queryset=None, **filters):
        """
        Convenience method to get filtered queryset

        Usage:
            qs = RawMaterialIssueFilter.get_filtered_queryset(
                issue_no='ISSUE-001',
                issue_start_date='2024-01-01',
                issue_end_date='2024-01-31',
                issue_status='issued',
                min_weight=10,
                max_weight=100)
        """
        if base_queryset is None:
            base_queryset = RawMaterialIssue.objects.all()

        return RawMaterialIssueFilter.apply_filters(base_queryset, filters)