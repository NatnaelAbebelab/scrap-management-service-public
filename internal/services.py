from helperFunctions.validations import is_valid_uuid, clean_tin


def process_scrap_excel(file, user):

    skipped_records = {
        "dropped_rows": [],
        "invalid_data": []
    }

    df = pd.read_excel(file, engine="openpyxl")

    required_columns = ["RECORD NO", "MATERIAL", "FIRM", "NET", "DATE1"]

    rows_to_drop = df[df[required_columns].isna().any(axis=1)]

    for index, row in rows_to_drop.iterrows():

        empty_cols = row[required_columns].isna()[row[required_columns].isna()].index.tolist()

        skipped_records["dropped_rows"].append({
            "row": index,
            "column": empty_cols,
            "case": f"Missing values in {empty_cols}"
        })

    df.dropna(subset=required_columns, inplace=True)

    records = df.to_dict(orient="records")

    created_count = 0

    for record in records:

        data = {
            "record_no": record["RECORD NO"],
            "plate_no": record.get("PLATE NO"),
            "first_weight": record.get("1ST WEIGHING"),
            "first_date": record.get("DATE1"),
            "first_time": record.get("TIME1"),
            "second_weight": record.get("2ND WEIGHING"),
            "second_date": record.get("DATE2"),
            "second_time": record.get("TIME2"),
            "net_weight": record.get("NET"),
            "firm": record.get("FIRM"),
            "material": record.get("MATERIAL"),
            "driver_name": record.get("Driver name "),
        }

        serializer = FactoryScrapUploadSerializer(data=data)

        if not serializer.is_valid():

            skipped_records["invalid_data"].append({
                "record_no": record.get("RECORD NO"),
                "errors": serializer.errors
            })

            continue

        validated = serializer.validated_data

        try:

            FactoryScrapMove.objects.create(
                record_no=validated["record_no"],
                plate_no=validated.get("plate_no"),
                first_weight=validated.get("first_weight"),
                first_date=validated.get("first_date"),
                first_time=validated.get("first_time"),
                second_weight=validated.get("second_weight"),
                second_date=validated.get("second_date"),
                second_time=validated.get("second_time"),
                net_weight=validated["net_weight"],
                agency=validated["firm"],
                material_type=validated["material"],
                driver_name=validated.get("driver_name"),
                created_by=user.username,
                updated_by=user.username,
            )

            created_count += 1

        except IntegrityError:

            skipped_records["invalid_data"].append({
                "record_no": record.get("RECORD NO"),
                "case": "Duplicate record number"
            })

    return {
        "created_records": created_count,
        "skipped_records": skipped_records
    }

def get_factory_scrap_records_service(user):
    """
    Fetch factory scrap records based on a role
    """

    role = get_user_role(user)

    if not role:
        raise ValueError("User role not found")

    allowed_status = Status.get_status_by_role(role)

    queryset = (
        FactoryScrapMove.objects
        .filter(status__in=allowed_status)
        .order_by("-record_time")
    )

    return queryset, allowed_status

def filter_factory_scrap_records_service(filters):
    queryset = (
        FactoryScrapMove.objects
        .filter(is_deleted=False)
        .order_by("-record_time")
    )

    # --- TIN Filter ---
    tin = filters.get("tin")

    if tin:
        agency = Agency.objects.filter(TIN=tin).first()
        if agency:
            queryset = queryset.filter(agency=tin)

    # --- Material Type ---
    material_type = filters.get("material_type")

    if material_type:
        queryset = queryset.filter(material_type__iexact=material_type)

    # --- Status Filters ---
    status = filters.get("status")

    if status:
        queryset = queryset.filter(status=status)

    # --- Plate Number ---
    plate_no = filters.get("plate_no")

    if plate_no:
        queryset = queryset.filter(plate_no__iexact=plate_no)

    # --- Date Filters ---
    start_date = filters.get("start_date")
    end_date = filters.get("end_date")

    if start_date or end_date:

        queryset = queryset.annotate(
            casted_first_date=ToDateTime("first_date")
        )

        if start_date:
            queryset = queryset.filter(
                casted_first_date__date__gte=start_date
            )

        if end_date:
            queryset = queryset.filter(
                casted_first_date__date__lte=end_date
            )

    return queryset

def create_agency(validated_data, user, today):

    agency = Agency.objects.create(
        fname=validated_data["first_name"].strip(),
        lname=validated_data["last_name"].strip(),
        TIN=validated_data["TIN"],
        business_name=validated_data["business_name"].strip(),
        created_by=user,
        updated_by=user
    )

    return agency

def get_agencies_service():
    """
    Fetch active agencies ordered by the latest record time
    Optimized using only() to reduce a database load
    """

    queryset = (
        Agency.objects
        .filter(is_deleted=False)
        .only(
            "first_name",
            "last_name",
            "TIN",
            "business_name",
            "record_time"
        )
        .order_by("-record_time")
    )

    return queryset

def update_agency_service(validated_data, user):

    agency = validated_data["agency_instance"]

    update_fields = {}

    fields = ["first_name", "last_name", "tin", "business_name", "agreement"]

    for field in fields:
        value = validated_data.get(field)

        if value:
            if field == "tin":
                update_fields["TIN"] = value
            else:
                update_fields[field] = value

    update_fields["updated_by"] = user

    for key, value in update_fields.items():
        setattr(agency, key, value)

    agency.save()

    return agency

def delete_agency_service(agency_id, user):
    if not is_valid_uuid(agency_id):
        raise ValueError(
            "Invalid agency ID"
        )
    agency = get_object_or_404(Agency, _id=agency_id)

    agency.delete()
    agency.updated_by = user
    return agency

def restore_agency_service(tin, user):
    if not clean_tin(tin):
        raise ValueError(
            "Invalid agency TIN"
        )

    agency = get_object_or_404(
        Agency.all_objects,
        TIN=tin,
        is_deleted=True
    )

    agency.restore()
    agency.updated_by = user

    return agency

def add_agreement_service(validated_data, user):
    agency_id = validated_data["agency"]
    material_type = validated_data["material_type"]
    ranges = validated_data["agreements"]
    proof_file_name = validated_data["agreement_proof"]

    agency = Agency.objects.filter(_id=agency_id).first()

    if not agency:
        raise ValueError("Agency not found")

    tin = agency.TIN

    agreement = Agreement.objects.filter(
        Q(TIN=tin) &
        Q(agency=agency_id) &
        Q(material_type__iexact=material_type)
    ).first()

    if agreement:
        raise ValueError("Agency agreement under material type already exists")

    # validate ranges
    for i, params in enumerate(ranges):

        min_weight = float(params.get("min_weight", 0))
        max_weight = params.get("max_weight")

        if max_weight == "MAX_FLAG":
            params["max_weight"] = MAX_FLOAT
            max_weight = MAX_FLOAT

        if min_weight > float(max_weight):
            raise ValueError("Minimum weight is greater than Maximum weight")

        if i < len(ranges) - 1:
            next_min = float(ranges[i + 1]["min_weight"])

            if float(max_weight) != next_min:
                raise ValueError(
                    f"Max weight of range {i+1} must equal min weight of range {i+2}"
                )

    agreement = Agreement.objects.create(
        agreement_name=validated_data["name"].lower(),
        agency=agency_id,
        TIN=tin,
        material_type=material_type,
        effective_date=validated_data["contract_details"]["effective_start_date"],
        duration=validated_data["contract_details"]["contract_duration_months"],
        agreement_proof=proof_file_name,
        created_by=user,
        updated_by=user
    )

    for params in ranges:
        AgreementRange.objects.create(
            agreement=agreement,
            agency=agency_id,
            min_weight=params["min_weight"],
            max_weight=params["max_weight"],
            rate=params["rate"],
            created_by=user,
            updated_by=user
        )

    return agreement

def update_agreement_service(validated_data, user):
    agreement_id = validated_data["agreement"]
    agency_id = validated_data["agency"]
    tin = clean_tin(validated_data["tin"])

    agreement = Agreement.objects.filter(_id=agreement_id).first()

    if not agreement:
        raise ValueError("Agreement does not exist")

    agency = Agency.objects.filter(
        _id=agency_id,
        TIN=tin
    ).first()

    if not agency:
        raise ValueError(f"Agency does not exist or TIN {tin} is mismatched")

    # Update fields dynamically
    update_fields = {}

    if validated_data.get("name"):
        update_fields["agreement_name"] = validated_data["name"]

    if validated_data.get("material_type"):
        update_fields["material_type"] = validated_data["material_type"]

    if validated_data.get("status"):
        status_obj = Status.get_status(validated_data["status"])
        update_fields["status"] = status_obj.status_value

    if validated_data.get("contract_details"):
        contract = validated_data["contract_details"]

        if contract.get("effective_start_date"):
            update_fields["effective_date"] = contract["effective_start_date"]

        if contract.get("contract_duration_months"):
            update_fields["duration"] = contract["contract_duration_months"]

    if validated_data.get("agreement_proof"):
        update_fields["agreement_proof"] = validated_data["agreement_proof"]

    if update_fields:

        update_fields["updated_by"] = user

        Agreement.objects.filter(_id=agreement_id).update(**update_fields)

        agreement.refresh_from_db()

    return agreement

def update_agreement_ranges(validated_data, user):
    """
    Service layer for updating agreement ranges
    """
    agreement_id = validated_data["agreement"]
    ranges = validated_data["ranges"]

    with transaction.atomic():
        for range_id, range_data in ranges.items():
            try:
                agreement_range = AgreementRange.objects.get(
                    _id=range_id,
                    agreement_id=agreement_id
                )
            except AgreementRange.DoesNotExist:
                raise ValueError(
                    f"Range {range_id} not found under this agreement"
                )

            update_fields = {
                "updated_by": user
            }

            if "min_weight" in range_data:
                update_fields["min_weight"] = range_data["min_weight"]

            if "max_weight" in range_data:
                update_fields["max_weight"] = range_data["max_weight"]

            if "rate" in range_data:
                update_fields["rate"] = range_data["rate"]

            # Remove if no real update fields
            if len(update_fields) > 3:
                AgreementRange.objects.filter(
                    _id=range_id
                ).update(**update_fields)

    return agreement_range

def delete_agreement_service(agreement_id):
    """
    Delete agreement and its related ranges
    """

    with transaction.atomic():
        if not is_valid_uuid(agreement_id):
            raise ValueError("Invalid agreement ID")

        # Get agreement
        agreement = get_object_or_404(
            Agreement,
            _id=agreement_id
        )

        # Delete related ranges first
        AgreementRange.objects.filter(
            agreement_id=agreement_id
        ).delete()

        # Delete agreement
        agreement.delete()

    return True

def filter_daily_scrap_move_aggregate(filters):
    """
    Service to filter daily scrap move aggregates
    """
    try:
        queryset = DailyScrapMoveAggregate.objects.all().order_by("-record_time")

        tin = filters.get("tin")
        material_type = filters.get("material_type")
        start_date = filters.get("start_date")
        end_date = filters.get("end_date")
        status = filters.get("status")

        # TIN filter
        if tin:
            agency = Agency.objects.filter(TIN=tin).first()
            if agency:
                queryset = queryset.filter(TIN=tin)

        # Material type filter
        if material_type:
            queryset = queryset.filter(material_type__iexact=material_type)

        # Status filtering
        if status:
            queryset = queryset.filter(status=status)

        # Date filtering
        queryset = queryset.annotate(
            casted_weight_date=ToFormalDate("weight_date")
        )

        if start_date:
            queryset = queryset.filter(casted_weight_date__gte=start_date)

        if end_date:
            queryset = queryset.filter(casted_weight_date__lte=end_date)

        return queryset

    except Exception as e:
        logger.error("Error occurred while filtering daily move aggregate: %s", e)
        raise FilterException("Error occurred while filtering daily move aggregate")

def calculate_daily_performance(filters):
    """
    Calculates driver performance within a given weight date range
    + returns summary and optional agency info
    """
    try:
        tin = filters.get("tin")
        plate_no = filters.get("plate_no")
        start_date = filters.get("start_date")
        end_date = filters.get("end_date")

        queryset = FactoryScrapMove.objects.annotate(
            first_date_as_date=ToDateTime(F("first_date"))
        )

        query_filter = Q()

        if tin:
            query_filter &= Q(agency=tin)

        if plate_no:
            query_filter &= Q(plate_no__iexact=plate_no)

        if start_date:
            query_filter &= Q(first_date_as_date__gte=start_date)

        if end_date:
            query_filter &= Q(first_date_as_date__lte=end_date)

        queryset = queryset.filter(query_filter)

        # Detailed aggregation (per plate_no + date)
        aggregated_data = (
            queryset
            .values("plate_no", "first_date")
            .annotate(
                total_first_weight=Round(Sum(Cast("first_weight", FloatField())), 2),
                total_second_weight=Round(Sum(Cast("second_weight", FloatField())), 2),
                total_net_weight=Round(Sum(Cast("net_weight", FloatField())), 2),
                total_records=Count("_id"),
                driver_names=ArrayAgg("driver_name", distinct=True),
            )
            .order_by("plate_no", "first_date")
        )

        # Summary (overall totals)
        summary = queryset.aggregate(
            total_first_weight=Round(Sum(Cast("first_weight", FloatField())), 2),
            total_second_weight=Round(Sum(Cast("second_weight", FloatField())), 2),
            total_net_weight=Round(Sum(Cast("net_weight", FloatField())), 2),
            total_records=Count("_id"),
        )

        # Normalize None → 0
        summary = {
            "total_first_weight": summary.get("total_first_weight") or 0,
            "total_second_weight": summary.get("total_second_weight") or 0,
            "total_net_weight": summary.get("total_net_weight") or 0,
            "total_records": summary.get("total_records") or 0,
        }

        # Agency info (if TIN provided)
        agency_info = None
        if tin:
            agency = Agency.objects.filter(TIN=tin, is_deleted=False).first()
            if agency:
                agency_info = {
                    "first_name": agency.first_name,
                    "last_name": agency.last_name,
                    "TIN": agency.TIN,
                    "business_name": agency.business_name,
                    "remaining_amount": agency.remaining_amount,
                    "paid_amount": agency.paid_amount,
                }

        return {
            "data": list(aggregated_data),
            "summary": summary,
            "agency_info": agency_info
        }

    except Exception:
        logger.error("Error occurred while calculating daily performance")
        raise Exception("Error occurred while calculating daily performance")

def approve_daily_scrap_move_records(valid_ids):
    """
    Approve daily scrap move records by supervisor
    """
    try:
        updated_count = (
            DailyScrapMoveAggregate.objects
            .filter(_id__in=valid_ids)
            .exclude(status="approved_manager")
            .update(
                status="approved"
            )
        )

        return updated_count

    except Exception as e:
        logger.error("Error occurred while approving daily scrap mov't: %s", e )
        raise Exception("Error occurred while approving daily scrap mov't")

def approve_factory_manager_records(valid_ids):
    """
    Factory manager approval for daily scrap move records
    """
    try:
        updated_count = (
            DailyScrapMoveAggregate.objects
            .filter(_id__in=valid_ids)
            .update(
                status="approved_manager",
                updated_at=today,
                record_time=timezone.now()
            )
        )

        return updated_count

    except Exception as e:
        logger.error("Error occurred while approving daily scrap mov't: %s", e)

        raise Exception(
            "Error occurred while approving daily scrap mov't"
        )

def pay_agency_finance_service(valid_ids):
    """
    Pay agency:
    - Update DailyScrapMoveAggregate status
    - Update Agency paid & remaining amounts
    """
    try:
        with transaction.atomic():
            # Aggregate total payment per TIN
            affected_agencies = (
                DailyScrapMoveAggregate.objects
                .filter(_id__in=valid_ids)
                .values("TIN")
                .annotate(
                    total_paid=Sum(Cast("net_price", FloatField()))
                )
            )

            # Update scrap move status
            updated_count = (
                DailyScrapMoveAggregate.objects
                .filter(_id__in=valid_ids)
                .update(
                    status="paid",
                    updated_at=today,
                    record_time=timezone.now()
                )
            )

            # Update Agency balances
            for agency_data in affected_agencies:
                tin = agency_data["TIN"]
                paid_amount = float(agency_data["total_paid"] or 0)

                Agency.objects.filter(TIN=tin).update(
                    paid_amount=Round(
                        Cast(F("paid_amount"), FloatField()) + paid_amount, 2
                    ),
                    remaining_amount=Round(
                        Cast(F("remaining_amount"), FloatField()) - paid_amount, 2
                    ),
                    updated_at=today,
                    record_time=timezone.now()
                )

        return {
            "updated_records": updated_count,
            "affected_agencies": len(affected_agencies)
        }

    except Exception as e:
        logger.exception("Error occurred while processing agency payment: %s", e)
        raise ServiceException("Error occurred while processing agency payment")