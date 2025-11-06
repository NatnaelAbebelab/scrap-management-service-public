from django_cron import CronJobBase, Schedule
from internal.tasks import daily_aggregate_scap_move
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DailyAggregateScrapMoveCronJob(CronJobBase):
    # Schedule to run every hour
    schedule = Schedule(run_every_mins=1)
    code = 'internal.scrap_processing_cron'

    def do(self):
        logger.info("Starting Scrap Processing Cron Job")
        try:
            print(f"[DEBUG] Cron Job Running at {datetime.now()}")
            daily_aggregate = daily_aggregate_scap_move()
            print(f"[DEBUG] Cron Job Completed at {datetime.now()}")
            return daily_aggregate
        except Exception as e:
            logger.error(f"Error in cron job: {e}", exc_info=True)
