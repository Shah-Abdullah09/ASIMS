import pytest


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    """Tests create many users; the production hasher is deliberately slow."""
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


@pytest.fixture(autouse=True)
def fresh_cache():
    """Rate limits are counted in the cache; every test starts with none used."""
    from django.core.cache import cache
    cache.clear()
