from django.urls import path
from .import views

urlpatterns = [
    path('upload/', views.upload_csv_file, name='upload_csv_file'),
    path('grn/', views.get_grn, name='get_grn'),
    
    path('change-status-bulk/', views.change_grn_status_bulk, name='change_grn_status_bulk'),
    path('change-status-individual/', views.change_grn_status_individual, name='change_grn_status_individual'),
    path('approve-grn-supervisor/', views.approve_grn_supervisor, name='approve_grn_supervisor'),
    
    path('decline-grn/', views.decline_grn, name='decline_grn'),
    path('decline-grn-supervisor/', views.decline_grn_supervisor, name='decline_grn_supervisor'),
    path('delete-grn/', views.delete_grn, name='delete_grn'),
    path('restore-grn/', views.restore_grn, name='restore_grn'),
    
    path('finance-grn/', views.get_grn_finance, name='get_grn_finance'),
    path('pay-customer/', views.pay_customer, name='pay_customer'),
    path('filter-grn/', views.filter_grn_records, name='filter_grn-records'),
    path('get-daily-purchase-performance/', views.get_daily_purchase_performance, name='get_daily_purchase_performance'),
    
    path('search/', views.search_record, name='search_record'),
    
    path('add-waste/', views.add_waste_deduction, name='add_waste_deduction'),
    path('edit-waste/', views.edit_waste_deduction, name='edit_waste_deduction')
]
