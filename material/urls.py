from django.urls import path
from . import views

urlpatterns = [
    path('add-melting-plant/', views.add_melting_plant, name='add-melting-plant'),
    path('get-melting-plants/', views.get_melting_plants, name='get-melting-plants'),
    path('edit-melting-plant/', views.edit_melting_plant, name='edit-melting-plant'),
    path('delete-melting-plant/<str:melting_plant_id>/', views.delete_melting_plant,name='delete-melting-plant'),
    
    path('add-material-requisition/', views.add_material_requisition, name='add-material-requisition'),
    path('get-material-requisitions/', views.get_material_requisitions, name='get-material-requisitions'),
    path('get-material-requisition/<str:requisition_id>/', views.get_material_requisition, name='get-material-requisition'),
    path('get-approved-material-requisitions/', views.get_approved_material_requisitions, name='get-approved-material-requisitions'),
    path('edit-material-requisition/', views.edit_material_requisition, name='edit-material-requisition'),
    path('approve-material-requisition/<str:requisition_id>/', views.approve_material_requisition, name='approve-material-requisition'),
    path('delete-material-requisition/<str:requisition_id>/', views.delete_material_requisition, name='delete-material-requisition'),

    path('add-raw-material-issue/', views.add_raw_material_issue, name='add-raw-material-issue'),
    path('get-raw-material-issues/', views.get_raw_material_issues, name='get-raw-material-issue'),
    path('get-raw-material-issue/<str:issue_id>/', views.get_raw_material_issue, name='get-raw-material-issue'),
    path('edit-raw-material-issue/', views.edit_raw_material_issue, name='edit-raw-material-issue'),
    path('change-status-issue/<str:issue_id>/', views.change_raw_material_issue_status, name='change-status-issue'),
    path('delete-raw-material-issue/<str:issue_id>/', views.delete_raw_material_issue, name='delete-raw-material-issue'),

    path('get-plants/', views.get_plants, name='get-plants'),
    
    #========= REPORTS ========
    path('paginated-material-requisition-report/', views.material_requisition_report, name='paginated-material-requisition-report'),
    path('material-requisition-report-export/', views.export_material_requisition_report,
         name='material-requisition-report-export'),
    path('paginated-material-issue-report/', views.material_issue_report, name='paginated-material-issue-report'),
    path('material-issue-report-export/', views.export_material_issue_report,
         name='material-issue-report-export'),
]