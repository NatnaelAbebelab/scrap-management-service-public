from django.urls import path
from .import views

urlpatterns = [
    path('active-rate/', views.get_active_rate, name='get_active_rates'),
    path('archive/', views.get_rate_archive, name='get_rate_archive'),
    path('add/', views.add_rate, name='add_rate'),
    path('delete/', views.delete_rate, name='delete_rate'),
    path('restore/', views.restore_rate, name='restore_rate'),
]