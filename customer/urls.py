from django.urls import path

from . import views

urlpatterns = [
    path('get-customers/', views.get_customers, name='get_customers'),
    path('add-customer/', views.add_customer, name='add_customer'),
    path('edit-customer/', views.edit_customer, name='edit_customer'),
    path('filter-customer/', views.filter_customer_TIN, name='filter_customer'),
    path('pay-customer/', views.pay_customer, name='pay_customer'),
    path('delete-customer/', views.delete_customer, name='delete_customer'),
]
