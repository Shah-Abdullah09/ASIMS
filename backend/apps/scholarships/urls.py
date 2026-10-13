from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('scholarships/applications', views.StudentApplicationViewSet, basename='scholarship-applications')

urlpatterns = [
    path('scholarships/cycles/open/', views.OpenCycleListView.as_view(), name='open-cycles'),
    path('', include(router.urls)),
]
