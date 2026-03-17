from django.urls import path
from .import views

urlpatterns = [
    path('upload-csv-file/', views.upload_excel_file, name='upload-csv-file'),
    path('get-factory-scrap-records/', views.get_factory_scrap_records, name='get-factory-scrap-records'),
    path('get-filtered-factory-scrap-records/', views.filter_factory_scrap_records, name='filter_factory_scrap_records'),
    
    path('add-agency/', views.add_agency, name='add-agency'),
    path('get-agencies/', views.get_agencies, name='get-agencies'),
    path('update-agency/', views.update_agency, name='update-agency'),
    path('delete-agency/<str:agency_id>/', views.delete_agency, name='delete-agency'),
    path('restore-agency/<str:tin>/', views.restore_agency, name='restore_agency'),
    
    path('add-agreement/', views.add_agreement, name='add-agreement'),
    path('get-agreements/', views.get_agreements, name='get-agreements'),
    path('update-agreement/', views.update_agreement, name='update-agreement'),
    path('update-agreement-range/', views.update_agreement_range, name='update-agreement-range'),
    path('delete-agreement/<str:agreement_id>/', views.delete_agreement, name='delete-agreement'),
    
    path('get-daily-scrap-move-aggregate/', views.get_daily_scrap_move_aggregate, name='get-daily-scrap-move-aggregate'),
    path('get-daily-performance-calculator/', views.get_daily_performance_calculation, name='get-daily-performance-calculation'),
    path('approve-record-supervisor/', views.approve_record_supervisor, name='approve-record-supervisor'),
    path('approve-record-factory-manager/', views.approve_record_factory_manager, name='approve_record_factory_manager'),
    path('pay-agency-finance/', views.pay_agency_finance, name='pay-agency-finance'),
]