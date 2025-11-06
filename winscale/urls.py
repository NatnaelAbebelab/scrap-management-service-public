from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.urls import path, include, re_path

schema_view = get_schema_view(
    openapi.Info(
        title="Winscale API",
        default_version="v1",
        description="API documentation for Winscale",
        terms_of_service="https://www.yourwebsite.com/terms/",
        contact=openapi.Contact(email="support@yourwebsite.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/grn/', include('grn.urls')),
    path('api/v1/rate/', include('rate.urls')),
    path('api/v1/customer/', include('customer.urls')),
    path('api/v1/user/', include('user.urls')),
    path('api/v1/role/', include('role.urls')),
    path('api/v1/report/', include('report.urls')),
    path('api/v1/internal/', include('internal.urls')),
    path('api/v1/cron/', include('cron.urls')),
    
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="redoc-ui"),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name="schema-json"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)