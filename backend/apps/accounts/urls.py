from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register('admin/users', views.UserAdminViewSet, basename='admin-users')
router.register('admin/departments', views.DepartmentAdminViewSet, basename='admin-departments')

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/verify-email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    path('auth/password/change/', views.PasswordChangeView.as_view(), name='password-change'),
    path('auth/password/forgot/', views.PasswordForgotView.as_view(), name='password-forgot'),
    path('auth/password/reset/', views.PasswordResetView.as_view(), name='password-reset'),
    path('departments/', views.PublicDepartmentListView.as_view(), name='departments'),
    path('', include(router.urls)),
]
