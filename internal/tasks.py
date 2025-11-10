from threading import Thread

from cron.tasks import process_aggregate_daily_factory_scrap_moves
from .models import FactoryScrapMove, Agreement, AgreementRange, DailyScrapMoveAggregate, ThreadTrack, Agency
from django.db.models import Sum,FloatField, F, Q, Max, DateTimeField, ExpressionWrapper, DateField
from django.db.models.functions import Cast
from helperFunctions.material_type import *
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
def daily_aggregate_scap_move():
    """
    Process new records from FactoryScrapMove that have a first_date greater than last_weight_time.
    """
    today = datetime.today().strftime('%Y-%m-%d')

    # Get the last processed weight time
    last_thread = ThreadTrack.objects.annotate(
        cast_last_weight_time=Cast('last_weight_time', DateTimeField())
    ).aggregate(max_weight_time=Max('cast_last_weight_time'))
    last_weight_time = last_thread["max_weight_time"]

    # Get new records that have first_date > last_weight_time
    new_records = FactoryScrapMove.objects.filter(first_date__gt=last_weight_time) if last_weight_time else FactoryScrapMove.objects.all()

    if not new_records.exists():
        return  # No new records to process

    # Aggregate new data
    result = (
        new_records
        .annotate(net_weight_float=Cast('net_weight', FloatField()))
        .values('agency', 'material_type', 'first_date')
        .annotate(total_net_weight=Sum('net_weight_float'))
    )
    processed_count = 0  # Track processed records
    latest_processed_date = last_weight_time.strftime('%Y-%m-%d') if isinstance(last_weight_time, datetime) else last_weight_time or "0000-00-00"

    for entry in result:
        agency_tin = entry['agency']
        material_type = entry['material_type']
        first_date_value = entry['first_date']
        
        # Ensure first_date is formatted correctly
        if isinstance(first_date_value, str):
            try:
                parsed_first_date = datetime.strptime(first_date_value, "%d.%m.%Y").strftime('%Y-%m-%d')
            except ValueError:
                continue  # Skip invalid date formats
        else:
            parsed_first_date = first_date_value.strftime('%Y-%m-%d')

        total_net_weight = entry['total_net_weight']
        net_price = 0
        # Get agreement for pricing
        agreement = Agreement.objects.filter(Q(TIN=agency_tin) & Q(material_type=material_type.lower())).first()
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
                # Save to DailyScrapMoveAggregate
                if not DailyScrapMoveAggregate.objects.filter(TIN=agency_tin, material_type=material_type.lower(), weight_date=parsed_first_date).exists():
                    daily_scrap = DailyScrapMoveAggregate(
                        TIN=agency_tin,
                        material_type=material_type.lower(),
                        weight_date=parsed_first_date,
                        daily_net_weight=total_net_weight,
                        rate=rate,
                        net_price=net_price,
                        created_at=today,
                        updated_at=today
                    )
                    daily_scrap.save()
                    # Update Agency model: increase remaining_amount by net_price
                    agency = Agency.objects.filter(TIN=agency_tin).first()
                    if agency:
                        agency.remaining_amount = round(float(agency.remaining_amount) + net_price, 2)
                        agency.updated_at = today
                        agency.save()

        processed_count += 1
        latest_processed_date = max(latest_processed_date, parsed_first_date)  # Track the latest processed date

    # Update ThreadTrack with the latest processed date only once
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