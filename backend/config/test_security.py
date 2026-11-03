"""Production security settings, the secret key guard, rate limits and the API schema."""
import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

import config.settings as settings_module
from apps.accounts.models import Role, User

LONG_KEY = 'x' * 50


@pytest.fixture
def reload_settings(monkeypatch):
    def load(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(settings_module)
    yield load
    monkeypatch.undo()
    importlib.reload(settings_module)


def test_production_turns_on_https_and_secure_cookies(reload_settings):
    s = reload_settings(DJANGO_DEBUG='False', DJANGO_SECRET_KEY=LONG_KEY)
    assert s.SECURE_SSL_REDIRECT and s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE
    assert s.SECURE_HSTS_SECONDS == 2592000 and s.SECURE_CONTENT_TYPE_NOSNIFF and s.X_FRAME_OPTIONS == 'DENY'


def test_development_keeps_plain_http(reload_settings):
    s = reload_settings(DJANGO_DEBUG='True')
    assert not s.SECURE_SSL_REDIRECT and not s.SESSION_COOKIE_SECURE and s.SECURE_HSTS_SECONDS == 0


@pytest.mark.parametrize('key', ['dev-only-insecure-key-change-me', 'change-me', 'short-key'])
def test_production_refuses_a_weak_secret_key(reload_settings, key):
    with pytest.raises(ImproperlyConfigured):
        reload_settings(DJANGO_DEBUG='False', DJANGO_SECRET_KEY=key)


def test_login_is_rate_limited(db):
    User.objects.create_user(email='ali@gmail.com', password='Str0ng-Passw0rd!', full_name='Ali', role=Role.STUDENT,
                             is_email_verified=True)
    client = APIClient()
    codes = [client.post('/api/v1/auth/login/', {'email': 'ali@gmail.com', 'password': 'wrong'}, format='json')
             .status_code for _ in range(11)]
    assert codes == [401] * 10 + [429]


def test_api_schema_has_no_errors(db):
    GENERATOR_STATS.reset()
    schema = SchemaGenerator().get_schema(request=None, public=True)
    assert '/api/v1/reports/scholarships/' in schema['paths'] and '/api/v1/auth/me/' in schema['paths']
    assert not GENERATOR_STATS._error_cache, list(GENERATOR_STATS._error_cache)
