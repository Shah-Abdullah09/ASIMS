from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models


class Role(models.TextChoices):
    STUDENT = 'student', 'Student'
    PLACEMENT_OFFICER = 'placement_officer', 'Placement Officer'
    DAC_MEMBER = 'dac_member', 'DAC Member'
    DIC = 'dic', 'Departmental Internship Coordinator'
    FACULTY_SUPERVISOR = 'faculty_supervisor', 'Faculty Supervisor'
    DIRECTOR = 'director', 'Director'
    REGISTRAR = 'registrar', 'Registrar'
    VICE_CHANCELLOR = 'vice_chancellor', 'Vice Chancellor'
    FINANCE_OFFICER = 'finance_officer', 'Finance Officer'
    ADMINISTRATOR = 'administrator', 'Administrator'


# Roles whose work is scoped to one department (DAC sees only its department's applicants)
DEPARTMENT_ROLES = (Role.DAC_MEMBER, Role.DIC)


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.code} - {self.name}'


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError('Email is required')
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('role', Role.ADMINISTRATOR)
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('is_email_verified', True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.STUDENT)
    department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.PROTECT, related_name='users'
    )
    # University registration number (students), e.g. 233585
    registration_id = models.CharField(
        max_length=6, unique=True, null=True, blank=True,
        validators=[RegexValidator(r'^\d{6}$', 'Registration ID must be exactly 6 digits.')],
    )
    is_email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django admin site access
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']
    objects = UserManager()

    class Meta:
        ordering = ['email']

    def __str__(self):
        return f'{self.email} ({self.role})'
