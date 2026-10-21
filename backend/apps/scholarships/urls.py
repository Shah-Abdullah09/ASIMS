from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('scholarships/applications', views.StudentApplicationViewSet, basename='scholarship-applications')
router.register('scholarships/review/applications', views.StaffApplicationViewSet, basename='scholarship-review')

urlpatterns = [
    path('scholarships/cycles/open/', views.OpenCycleListView.as_view(), name='open-cycles'),
    path('scholarships/documents/<int:doc_id>/download/', views.DocumentDownloadView.as_view(),
         name='scholarship-document-download'),
    path('scholarships/declarations/<int:declaration_id>/scan/', views.DeclarationScanDownloadView.as_view(),
         name='declaration-scan-download'),
    path('scholarships/declarations/<int:declaration_id>/receive/', views.DeclarationReceiveView.as_view(),
         name='declaration-receive'),
    path('', include(router.urls)),
]
