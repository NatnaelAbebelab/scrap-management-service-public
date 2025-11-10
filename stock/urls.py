from django.urls import path
from . import views

urlpatterns = [
    path('add-beginning-balance/', views.add_beginning_balance, name='add-beginning-balance'),
    path('get-stock-summery/', views.get_active_balance_summary, name='get-stock-summery'),
    path('get-stock-balance/', views.get_stock_balance, name='get-stock-balance'),
    path('get-stock-report/', views.get_stock_report, name='get-stock-report'),
    path('get-stock-card/', views.get_stock_card, name='get-stock-card'),
]