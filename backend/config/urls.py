from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def health(request):
    return JsonResponse({'status': 'ok', 'service': 'asims-api'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/health/', health, name='health'),
    path('api/v1/', include('apps.accounts.urls')),
    path('api/v1/', include('apps.scholarships.urls')),
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='docs'),
]
