from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('internships/requests', views.StudentRequestViewSet, basename='internship-requests')

urlpatterns = [
    path('internships/files/<int:req_id>/<str:kind>/', views.InternshipFileView.as_view(), name='internship-file'),
    path('', include(router.urls)),
]
