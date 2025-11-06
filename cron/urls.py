from django.urls import path
from .views import TaskClass

urlpatterns = [
    path('run-cron/', TaskClass.as_view(), name='run-cron'),
]
