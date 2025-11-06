from django.urls import path
from django.views.generic.base import TemplateView
from django.conf import settings
from django.conf.urls.static import static
from .import views

urlpatterns = [
    path('add', views.add_role, name='add_role'),
    path('get', views.get_roles, name='get_roles'),
    path('update', views.update_role, name='update_role'),
    path('delete', views.delete_role, name='delete_role'),
]