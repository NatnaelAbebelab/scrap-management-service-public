from django_cron import CronJobBase, Schedule
from datetime import datetime
from .tasks import process_aggregate_daily_factory_scrap_moves
from rest_framework.decorators import APIView, permission_classes
from rest_framework.permissions import IsAuthenticated
from utils.permissions import role_required
from rest_framework.response import Response
from rest_framework import status
import logging, traceback

logger = logging.getLogger(__name__)

class MyCronJob(CronJobBase):
    # Define how often it runs
    RUN_EVERY_MINS = 1
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    # Unique identifier for the cron job
    code = "cron.my_cron_job"  # This should be a unique string
    
    def do(self):
        now = datetime.now()
        logger.error(f"Now is {now}")
        try:
            # 24 hr format 
            if now.hour == 10 and 0 <= now.minute <= 59:
                print(f"Cron executed at {now}")
                logger.error(f"Cron executed at {now}")
                process_aggregate_daily_factory_scrap_moves()
            else:
                print(f"Checked at {now}, not time yet")
                logger.error(f"Checked at {now}, not time yet")
        except Exception as e:
            print("Cron Job Failed:")
            logger.error(f"Cron Job Failed: {e}")
            logger.error(traceback.format_exc())

@permission_classes([IsAuthenticated, role_required(["super_admin"])])
class TaskClass(APIView):
    def post(self, request):
        try:
            result = process_aggregate_daily_factory_scrap_moves()
            return Response({"message": "Function executed", "result": result}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error occurred while processing daily factor scrap move aggregate: %s", e)
            return Response({"message": "Function executed", "result": result}, status=status.HTTP_404_NOT_FOUND)