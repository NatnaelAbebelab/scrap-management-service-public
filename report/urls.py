from django.urls import path
from .import views

urlpatterns = [
    path('aggregate-report/', views.aggregate_report, name='aggregate_report'),
    path('plain-report/', views.plain_report, name='plain_report'),
    path('general-metrics/', views.general_metrics, name='general_metrics'),
    path('scrap-grade-percentage/', views.scrap_grade_percentage, name='scrap_grade_percentage'),
    path('yearly-purchase-report/', views.yearly_purchase_report, name='yearly_purchase_report'),
    
    path('internal-aggregate-report/', views.internal_process_report, name='internal_process_report'),
    path('internal-general-metrics/', views.internal_general_metrics, name='internal_general_metrics'),
    path('yearly-internal-scrap-move/', views.yearly_internal_scrap_move, name='yearly_internal_scrap_move'),
]