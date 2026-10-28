from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.audit.log import record
from apps.audit.models import AuditAction

from .models import Department, Role, User
from .permissions import has_role
from .serializers import (AdminUserSerializer, DepartmentSerializer, LoginSerializer, ProfileUpdateSerializer,
                          RegisterSerializer, UserSerializer, VerifyEmailSerializer)

VERIFY_SALT = 'asims-email-verification'


def make_verification_token(user):
    return signing.dumps({'uid': user.pk}, salt=VERIFY_SALT)


def send_verification_email(user):
    link = f'{settings.FRONTEND_URL}/verify-email?token={make_verification_token(user)}'
    send_mail(
        'Verify your ASIMS account',
        f'Hello {user.full_name},\n\nPlease verify your email address:\n{link}\n\n'
        'This link expires in 48 hours.',
        None,
        [user.email],
    )


class RegisterView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        record(AuditAction.REGISTER, request=request, actor=user, target=user, department=user.department_id)
        send_verification_email(user)
        return Response(
            {'detail': 'Account created. Check your email to verify your address.'},
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = VerifyEmailSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            data = signing.loads(
                serializer.validated_data['token'],
                salt=VERIFY_SALT,
                max_age=settings.EMAIL_VERIFICATION_MAX_AGE,
            )
            user = User.objects.get(pk=data['uid'])
        except (signing.BadSignature, User.DoesNotExist):
            return Response({'detail': 'This verification link is invalid or has expired.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified'])
            record(AuditAction.VERIFY_EMAIL, request=request, actor=user, target=user)
        return Response({'detail': 'Email verified. You can now log in.'})


class LoginView(TokenObtainPairView):
    """Every attempt is audited: successes, and failures with the reason (never the password)."""

    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        email = str(request.data.get('email', ''))[:254].strip().lower()
        try:
            response = super().post(request, *args, **kwargs)
        except (AuthenticationFailed, InvalidToken) as exc:
            # The account, if the email exists, so repeated failures against one account stand out
            record(AuditAction.LOGIN_FAILED, request=request, actor=User.objects.filter(email=email).first(),
                   email=email, reason=str(exc.detail))
            raise
        user = User.objects.get(pk=response.data['user']['id'])
        record(AuditAction.LOGIN, request=request, actor=user, target=user)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record(AuditAction.USER_UPDATED, request=request, target=request.user, fields=sorted(serializer.validated_data))
        return Response(UserSerializer(request.user).data)


class PublicDepartmentListView(ListAPIView):
    """Active departments, used by the registration form."""

    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = DepartmentSerializer
    queryset = Department.objects.filter(is_active=True)
    pagination_class = None


class DepartmentAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [has_role(Role.ADMINISTRATOR)]
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()

    def perform_create(self, serializer):
        department = serializer.save()
        record(AuditAction.DEPARTMENT_CHANGED, request=self.request, target=department, change='created',
               **serializer.data)

    def perform_update(self, serializer):
        department = serializer.save()
        record(AuditAction.DEPARTMENT_CHANGED, request=self.request, target=department, change='updated',
               **serializer.data)

    def perform_destroy(self, instance):
        record(AuditAction.DEPARTMENT_CHANGED, request=self.request, target=instance, change='deleted',
               code=instance.code, name=instance.name)
        instance.delete()


class UserAdminViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """No delete: accounts are deactivated so audit history is preserved."""

    permission_classes = [has_role(Role.ADMINISTRATOR)]
    serializer_class = AdminUserSerializer
    queryset = User.objects.select_related('department')

    @staticmethod
    def _changes(validated):
        # Field names and new values; a password is noted but never stored
        changes = {k: (v.pk if hasattr(v, 'pk') else v) for k, v in validated.items() if k != 'password'}
        if 'password' in validated:
            changes['password'] = 'set'
        return changes

    def perform_create(self, serializer):
        changes = self._changes(serializer.validated_data)  # before save, which removes the password
        user = serializer.save()
        record(AuditAction.USER_CREATED, request=self.request, target=user, **changes)

    def perform_update(self, serializer):
        changes = self._changes(serializer.validated_data)
        user = serializer.save()
        record(AuditAction.USER_UPDATED, request=self.request, target=user, **changes)
