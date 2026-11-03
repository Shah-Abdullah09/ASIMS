from django.urls import path

from . import views

urlpatterns = [
    path('admin/audit-log/', views.AuditLogListView.as_view(), name='audit-log'),
    path('admin/audit-log/actions/', views.AuditActionListView.as_view(), name='audit-actions'),
]
