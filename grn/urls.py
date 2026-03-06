from django.urls import path
from .import views

urlpatterns = [
    path('upload/', views.upload_csv_file, name='upload_csv_file'),
    path('grn/', views.get_grn, name='get_grn'),
    
    path('change-grn-status/', views.change_grn_status, name='change_grn_status'),

    path('rollback-grn-status/', views.rollback_grn, name='rollback_grn'),
    path('delete-grn/<str:_id>/', views.delete_grn, name='delete_grn'),
    path('restore-grn/<str:_id>/', views.restore_grn, name='restore_grn'),
    
    path('finance-grn/', views.get_grn_finance, name='get_grn_finance'),
    path('pay-customer/', views.pay_customer, name='pay_customer'),
    path('filter-grn/', views.filter_grn_records, name='filter_grn-records'),
    path('get-daily-purchase-performance/', views.get_daily_purchase_performance, name='get_daily_purchase_performance'),
    
    path('search/', views.search_record, name='search_record'),
    
    path('add-waste/', views.add_waste_deduction, name='add_waste_deduction'),
    path('edit-waste/', views.edit_waste_deduction, name='edit_waste_deduction'),

    path('initialize-grn-serial-number/<int:initial_serial_number>/', views.initialize_grn_serial_number, name='initialize-grn-serial-number'),
    path('get-grn-serial-numbers/', views.get_grn_serial_numbers, name='get-grn-serial-numbers'),
    path('get-scrap-receipt/<str:record_no>/', views.get_scrap_receipt, name='get-scrap-receipt'),
]
