from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView, TokenVerifyView
from django.contrib.auth import views as auth_views
from django.urls import path
from .import views

urlpatterns = [
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('api/token/verify/', TokenVerifyView.as_view(), name="token_verify"),
    path('add/', views.add_user, name='add_user'),
    path('get/', views.get_users, name='get_users'),
    path('update/', views.update_user, name='update_user'),
    path('delete/<str:user_id>/', views.delete_user, name='delete_user'),
    path('restore/', views.restore_user, name='restore_user'),
    path('login/', views.user_login, name='user_login'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('get-roles/', views.get_role_options, name='get-role'),
    path('get-me/<str:user_id>/', views.get_me, name='get-me'),
    path("csrf/", views.csrf_token_view),
]