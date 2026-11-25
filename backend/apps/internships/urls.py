from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('internships/requests', views.StudentInternshipViewSet, basename='internship-requests')
router.register('internships/companies', views.CompanyViewSet, basename='internship-companies')

urlpatterns = [
    path('', include(router.urls)),
]
