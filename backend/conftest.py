import pytest


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    """Tests create many users; the production hasher is deliberately slow."""
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
