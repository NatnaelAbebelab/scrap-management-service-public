# internal/management/commands/run_daily_aggregate_scrap_move.py
from django.core.management.base import BaseCommand
from internal.cron import DailyAggregateScrapMoveCronJob

class Command(BaseCommand):
    help = 'Runs the DailyAggregateScrapMoveCronJob'

    def handle(self, *args, **kwargs):
        # Instantiate the cron job and run the `do()` method
        job = DailyAggregateScrapMoveCronJob()
        job.do()
        self.stdout.write(self.style.SUCCESS('Successfully ran the cron job.'))