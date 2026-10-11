from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import DEPARTMENT_ROLES, Department, Role, User


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'is_active']


class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role', 'department', 'department_name',
                  'is_email_verified']
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    """Student self-registration. Staff accounts are created by the Administrator."""

    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.filter(is_active=True))

    def validate_email(self, value):
        value = value.lower()
        domain = settings.STUDENT_EMAIL_DOMAIN.lower()
        if domain and not value.endswith('@' + domain):
            raise serializers.ValidationError(f'Students must register with an @{domain} email address.')
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate(self, attrs):
        candidate = User(email=attrs['email'], full_name=attrs['full_name'])
        validate_password(attrs['password'], candidate)
        return attrs

    def create(self, validated):
        return User.objects.create_user(role=Role.STUDENT, **validated)


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)  # raises for wrong credentials or inactive users
        if not self.user.is_email_verified:
            raise AuthenticationFailed('Please verify your email address before logging in.')
        data['user'] = UserSerializer(self.user).data
        return data


class AdminUserSerializer(serializers.ModelSerializer):
    """Used by the Administrator to create and manage any account."""

    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role', 'department', 'is_active',
                  'is_email_verified', 'password', 'date_joined']
        read_only_fields = ['id', 'is_email_verified', 'date_joined']

    def validate_email(self, value):
        value = value.lower()
        qs = User.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate(self, attrs):
        role = attrs.get('role', getattr(self.instance, 'role', None))
        department = attrs.get('department', getattr(self.instance, 'department', None))
        if role in DEPARTMENT_ROLES and department is None:
            raise serializers.ValidationError({'department': 'This role must be linked to a department.'})
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'A password is required.'})
        if attrs.get('password'):
            validate_password(attrs['password'], self.instance)
        return attrs

    def create(self, validated):
        password = validated.pop('password')
        return User.objects.create_user(password=password, is_email_verified=True, **validated)

    def update(self, instance, validated):
        password = validated.pop('password', None)
        for field, value in validated.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
