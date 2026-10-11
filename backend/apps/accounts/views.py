from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from rest_framework import mixins, status, viewsets
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Department, Role, User
from .permissions import has_role
from .serializers import (AdminUserSerializer, DepartmentSerializer, LoginSerializer,
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
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        return Response({'detail': 'Email verified. You can now log in.'})


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
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


class UserAdminViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """No delete: accounts are deactivated so audit history is preserved."""

    permission_classes = [has_role(Role.ADMINISTRATOR)]
    serializer_class = AdminUserSerializer
    queryset = User.objects.select_related('department')
