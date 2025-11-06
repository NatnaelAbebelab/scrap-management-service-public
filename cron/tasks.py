from threading import Thread
from internal.models import FactoryScrapMove, Agreement, AgreementRange, DailyScrapMoveAggregate, ThreadTrack, Agency
from django.db.models import Sum, FloatField, F, Q, Max, DateTimeField
from django.db.models.functions import Cast
from django.utils import timezone
from helperFunctions.material_type import *
from helperFunctions.validations import *
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')

def process_aggregate_daily_factory_scrap_moves():
    # Get the last processed weight time from ThreadTrack
    last_thread = ThreadTrack.objects.annotate(
        cast_last_weight_time=Cast("last_weight_time", DateTimeField())
    ).aggregate(max_weight_time=Max("cast_last_weight_time"))
    last_weight_time = last_thread["max_weight_time"]

    def process_entries(records, save_thread_track=False):
        processed_count = 0
        latest_processed_date = None
        is_reprocessing = not save_thread_track

        # Aggregate FactoryScrapMove records with status="new"
        result = (
            records
            .filter(status="new")
            .annotate(net_weight_float=Cast("net_weight", FloatField()))
            .values("agency", "material_type", "first_date")
            .annotate(total_net_weight=Sum("net_weight_float"))
        )

        for entry in result:
            agency_tin = entry["agency"]
            material_type = entry["material_type"]
            first_date_value = entry["first_date"]

            # Parse and normalize date to PostgreSQL-compatible format (YYYY-MM-DD)
            if isinstance(first_date_value, str):
                try:
                    parsed_first_date = datetime.strptime(first_date_value, "%d.%m.%Y").strftime("%Y-%m-%d")
                except ValueError:
                    continue  # Skip invalid date formats
            else:
                parsed_first_date = first_date_value.strftime("%Y-%m-%d")

            total_net_weight = entry["total_net_weight"]
            net_price = 0

            # Check for existing DailyScrapMoveAggregate record
            existing_qs = DailyScrapMoveAggregate.objects.filter(
                TIN=agency_tin,
                material_type=material_type.lower(),
                weight_date=parsed_first_date
            )

            # If reprocessing old records, delete existing aggregates regardless of status
            if is_reprocessing:
                existing_qs.delete()
            # If not reprocessing, handle based on status
            else:
                existing_new = existing_qs.filter(status="new")
                if existing_new.exists():
                    # Rework: Delete existing aggregate with status="new" and recalculate
                    existing_new.delete()
                else:
                    # If status is not "new", skip and process remaining records separately later
                    continue

            # Pricing logic
            agreement = Agreement.objects.filter(
                Q(TIN=agency_tin) & Q(material_type=material_type.lower())
            ).first()

            if agreement:
                agreement_range = AgreementRange.objects.annotate(
                    min_weight_numeric=Cast(F("min_weight"), FloatField()),
                    max_weight_numeric=Cast(F("max_weight"), FloatField())
                ).filter(
                    agreement=agreement,
                    min_weight_numeric__lte=total_net_weight,
                    max_weight_numeric__gt=total_net_weight
                ).first()

                if agreement_range:
                    rate = float(agreement_range.rate)
                    net_price = total_net_weight * rate

                    # Save new DailyScrapMoveAggregate record
                    daily_scrap = DailyScrapMoveAggregate.objects.create(
                        TIN=agency_tin,
                        material_type=material_type.lower(),
                        weight_date=parsed_first_date,
                        daily_net_weight=total_net_weight,
                        rate=rate,
                        net_price=net_price,
                        status="new",  # Set status to "new"
                        created_at=today,
                        updated_at=today,
                    )

                    # Update Agency.remaining_amount
                    agency = Agency.objects.filter(TIN=agency_tin).first()
                    if agency:
                        agency.remaining_amount = round(float(agency.remaining_amount) + net_price, 2)
                        agency.updated_at = today
                        agency.record_time = timezone.now()
                        agency.save()

                    # Optionally update FactoryScrapMove status to "processed"
                    FactoryScrapMove.objects.filter(
                        agency=agency_tin,
                        material_type=material_type,
                        first_date=first_date_value,
                        status="new"
                    ).update(status="processed", updated_at=timezone.now())

            processed_count += 1
            latest_processed_date = max(latest_processed_date or parsed_first_date, parsed_first_date)

        # Process remaining unaggregated FactoryScrapMove records for non-"new" aggregates
        if not is_reprocessing:
            remaining_records = (
                FactoryScrapMove.objects
                .filter(status="new")
                .exclude(
                    Q(agency__in=DailyScrapMoveAggregate.objects.filter(status="new").values("TIN"),
                      material_type__in=DailyScrapMoveAggregate.objects.filter(status="new").values("material_type"),
                      first_date__in=DailyScrapMoveAggregate.objects.filter(status="new").values("weight_date"))
                )
                .annotate(net_weight_float=Cast("net_weight", FloatField()))
                .values("agency", "material_type", "first_date")
                .annotate(total_net_weight=Sum("net_weight_float"))
            )

            for entry in remaining_records:
                agency_tin = entry["agency"]
                material_type = entry["material_type"]
                first_date_value = entry["first_date"]

                if isinstance(first_date_value, str):
                    try:
                        parsed_first_date = datetime.strptime(first_date_value, "%d.%m.%Y").strftime("%Y-%m-%d")
                    except ValueError:
                        continue
                else:
                    parsed_first_date = first_date_value.strftime("%Y-%m-%d")

                total_net_weight = entry["total_net_weight"]
                net_price = 0

                # Skip if already processed in this batch
                if DailyScrapMoveAggregate.objects.filter(
                    TIN=agency_tin,
                    material_type=material_type.lower(),
                    weight_date=parsed_first_date
                ).exists():
                    continue

                agreement = Agreement.objects.filter(
                    Q(TIN=agency_tin) & Q(material_type=material_type.lower())
                ).first()

                if agreement:
                    agreement_range = AgreementRange.objects.annotate(
                        min_weight_numeric=Cast(F("min_weight"), FloatField()),
                        max_weight_numeric=Cast(F("max_weight"), FloatField())
                    ).filter(
                        agreement=agreement,
                        min_weight_numeric__lte=total_net_weight,
                        max_weight_numeric__gt=total_net_weight
                    ).first()

                    if agreement_range:
                        rate = float(agreement_range.rate)
                        net_price = total_net_weight * rate

                        # Create new DailyScrapMoveAggregate for remaining records
                        DailyScrapMoveAggregate.objects.create(
                            TIN=agency_tin,
                            material_type=material_type.lower(),
                            weight_date=parsed_first_date,
                            daily_net_weight=total_net_weight,
                            rate=rate,
                            net_price=net_price,
                            status="new",
                            created_at=today,
                            updated_at=today,
                        )

                        # Update Agency.remaining_amount
                        agency = Agency.objects.filter(TIN=agency_tin).first()
                        change_in_amount = net_price
                        if agency:
                            agency.remaining_amount = round(float(agency.remaining_amount) + change_in_amount, 2)
                            agency.updated_at = today
                            agency.record_time = timezone.now()
                            agency.save()

                        # Optionally update FactoryScrapMove status
                        FactoryScrapMove.objects.filter(
                            agency=agency_tin,
                            material_type=material_type,
                            first_date=first_date_value,
                            status="new"
                        ).update(status="processed", updated_at=timezone.now())

                processed_count += 1
                latest_processed_date = max(latest_processed_date or parsed_first_date, parsed_first_date)

        # Save ThreadTrack for new data
        if save_thread_track and processed_count > 0:
            ThreadTrack.objects.create(
                last_weight_time=latest_processed_date,
                record_count=processed_count,
                execution_period=today
            )

    # Step 1: Fix and process older records (< last_weight_time)
    if last_weight_time:
        old_records = FactoryScrapMove.objects.annotate(
            casted_first_date=ToTimestamp(F("first_date"))
        ).filter(casted_first_date__lt=last_weight_time)
        
        if old_records.exists():
            process_entries(old_records, save_thread_track=False)

    # Step 2: Process new records (> last_weight_time)
    new_records = FactoryScrapMove.objects.annotate(
        casted_first_date=ToDate("first_date")
    ).filter(casted_first_date__gt=last_weight_time) if last_weight_time else FactoryScrapMove.objects.all()

    if new_records.exists():
        process_entries(new_records, save_thread_track=True)

def daily_aggregate_scrap_move():
    """
    Process new records from FactoryScrapMove that have a first_date greater than last_weight_time and status="new".
    """
    today = datetime.today().strftime('%Y-%m-%d')

    # Get the last processed weight time
    last_thread = ThreadTrack.objects.annotate(
        cast_last_weight_time=Cast('last_weight_time', DateTimeField())
    ).aggregate(max_weight_time=Max('cast_last_weight_time'))
    last_weight_time = last_thread["max_weight_time"]

    # Get new records with status="new"
    new_records = FactoryScrapMove.objects.filter(
        first_date__gt=last_weight_time, status="new"
    ) if last_weight_time else FactoryScrapMove.objects.filter(status="new")

    if not new_records.exists():
        return

    # Aggregate new data
    result = (
        new_records
        .annotate(net_weight_float=Cast('net_weight', FloatField()))
        .values('agency', 'material_type', 'first_date')
        .annotate(total_net_weight=Sum('net_weight_float'))
    )
    processed_count = 0
    latest_processed_date = last_weight_time.strftime('%Y-%m-%d') if isinstance(last_weight_time, datetime) else last_weight_time or "0000-00-00"

    for entry in result:
        agency_tin = entry['agency']
        material_type = entry['material_type']
        first_date_value = entry['first_date']
        
        # Parse first_date
        if isinstance(first_date_value, str):
            try:
                parsed_first_date = datetime.strptime(first_date_value, "%d.%m.%Y").strftime('%Y-%m-%d')
            except ValueError:
                continue
        else:
            parsed_first_date = first_date_value.strftime('%Y-%m-%d')

        total_net_weight = entry['total_net_weight']
        net_price = 0

        # Check for existing DailyScrapMoveAggregate
        existing_qs = DailyScrapMoveAggregate.objects.filter(
            TIN=agency_tin,
            material_type=material_type.lower(),
            weight_date=parsed_first_date
        )

        change_in_amount = 0
        if existing_qs.filter(status="new").exists():
            # Rework: Delete and recalculate for status="new"
            existing = existing_qs.filter(status="new").first()
            change_in_amount = -existing.net_price if existing else 0  # Subtract old net_price
            existing_qs.filter(status="new").delete()
        elif existing_qs.exists():
            # Skip if status is not "new" (will process remaining records separately)
            continue

        # Pricing logic
        agreement = Agreement.objects.filter(
            Q(TIN=agency_tin) & Q(material_type=material_type.lower())
        ).first()

        if agreement:
            agreement_range = AgreementRange.objects.annotate(
                min_weight_numeric=Cast(F('min_weight'), FloatField()),
                max_weight_numeric=Cast(F('max_weight'), FloatField())
            ).filter(
                agreement=agreement,
                min_weight_numeric__lte=total_net_weight,
                max_weight_numeric__gte=total_net_weight
            ).first()

            if agreement_range:
                rate = float(agreement_range.rate)
                net_price = total_net_weight * rate
                change_in_amount += net_price  # Add new net_price

                # Save to DailyScrapMoveAggregate
                daily_scrap = DailyScrapMoveAggregate(
                    TIN=agency_tin,
                    material_type=material_type.lower(),
                    weight_date=parsed_first_date,
                    daily_net_weight=total_net_weight,
                    rate=rate,
                    net_price=net_price,
                    status="new",
                    created_at=today,
                    updated_at=today
                )
                daily_scrap.save()

                # Update Agency.remaining_amount
                agency = Agency.objects.filter(TIN=agency_tin).first()
                if agency:
                    agency.remaining_amount = round(float(agency.remaining_amount) + change_in_amount, 2)
                    agency.updated_at = today
                    agency.record_time = timezone.now()
                    agency.save()

                # Optionally update FactoryScrapMove status
                FactoryScrapMove.objects.filter(
                    agency=agency_tin,
                    material_type=material_type,
                    first_date=first_date_value,
                    status="new"
                ).update(status="processed", updated_at=timezone.now())

        processed_count += 1
        latest_processed_date = max(latest_processed_date, parsed_first_date)

    # Process remaining unaggregated records for non-"new" aggregates
    remaining_records = (
        new_records
        .exclude(
            Q(agency__in=DailyScrapMoveAggregate.objects.filter(status="new").values("TIN"),
              material_type__in=DailyScrapMoveAggregate.objects.filter(status="new").values("material_type"),
              first_date__in=DailyScrapMoveAggregate.objects.filter(status="new").values("weight_date"))
        )
        .annotate(net_weight_float=Cast("net_weight", FloatField()))
        .values("agency", "material_type", "first_date")
        .annotate(total_net_weight=Sum("net_weight_float"))
    )

    for entry in remaining_records:
        agency_tin = entry["agency"]
        material_type = entry["material_type"]
        first_date_value = entry["first_date"]

        if isinstance(first_date_value, str):
            try:
                parsed_first_date = datetime.strptime(first_date_value, "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                continue
        else:
            parsed_first_date = first_date_value.strftime("%Y-%m-%d")

        total_net_weight = entry["total_net_weight"]
        net_price = 0

        # Skip if already processed
        if DailyScrapMoveAggregate.objects.filter(
            TIN=agency_tin,
            material_type=material_type.lower(),
            weight_date=parsed_first_date
        ).exists():
            continue

        agreement = Agreement.objects.filter(
            Q(TIN=agency_tin) & Q(material_type=material_type.lower())
        ).first()

        if agreement:
            agreement_range = AgreementRange.objects.annotate(
                min_weight_numeric=Cast(F("min_weight"), FloatField()),
                max_weight_numeric=Cast(F("max_weight"), FloatField())
            ).filter(
                agreement=agreement,
                min_weight_numeric__lte=total_net_weight,
                max_weight_numeric__gte=total_net_weight
            ).first()

            if agreement_range:
                rate = float(agreement_range.rate)
                net_price = total_net_weight * rate

                # Create new DailyScrapMoveAggregate
                DailyScrapMoveAggregate.objects.create(
                    TIN=agency_tin,
                    material_type=material_type.lower(),
                    weight_date=parsed_first_date,
                    daily_net_weight=total_net_weight,
                    rate=rate,
                    net_price=net_price,
                    status="new",
                    created_at=today,
                    updated_at=today,
                )

                # Update Agency.remaining_amount
                agency = Agency.objects.filter(TIN=agency_tin).first()
                if agency:
                    agency.remaining_amount = round(float(agency.remaining_amount) + net_price, 2)
                    agency.updated_at = today
                    agency.record_time = timezone.now()
                    agency.save()

                # Optionally update FactoryScrapMove status
                FactoryScrapMove.objects.filter(
                    agency=agency_tin,
                    material_type=material_type,
                    first_date=first_date_value,
                    status="new"
                ).update(status="processed", updated_at=timezone.now())

        processed_count += 1
        latest_processed_date = max(latest_processed_date, parsed_first_date)

    # Update ThreadTrack
    if processed_count > 0:
        ThreadTrack.objects.create(
            last_weight_time=latest_processed_date,
            record_count=processed_count,
            execution_period=today
        )

def process_in_background():
    """Run the background task in a separate thread."""
    thread = Thread(target=process_aggregate_daily_factory_scrap_moves)
    thread.start()