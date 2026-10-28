"""One-time links for setting a password: "forgot password" and the Administrator's staff invitation.

A link is signed (it cannot be forged or edited), expires (1 hour for a reset, 72 hours for an invitation)
and carries a fingerprint of the user's current password, so it stops working as soon as it has been used
or the password has changed in any other way."""
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import User

SALT = 'asims-password-link'
RESET, INVITE = 'reset', 'invite'
LIFETIME = {RESET: 60 * 60, INVITE: 72 * 60 * 60}  # seconds


def _fingerprint(user):
    return salted_hmac(SALT, f'{user.pk}:{user.password}').hexdigest()[:24]


def make_password_token(user, purpose):
    return signing.dumps({'uid': user.pk, 'p': purpose, 'f': _fingerprint(user)}, salt=SALT)


def read_password_token(token):
    """(user, purpose) for a valid link, otherwise None (forged, expired, already used or inactive account)."""
    try:
        data = signing.loads(token, salt=SALT, max_age=max(LIFETIME.values()))
        purpose = data['p']
        signing.loads(token, salt=SALT, max_age=LIFETIME[purpose])  # the limit of this kind of link
        user = User.objects.get(pk=data['uid'], is_active=True)
    except (signing.BadSignature, KeyError, TypeError, User.DoesNotExist):
        return None
    if not constant_time_compare(data['f'], _fingerprint(user)):
        return None
    return user, purpose


def password_link(user, purpose):
    return f'{settings.FRONTEND_URL}/reset-password?token={make_password_token(user, purpose)}'


def send_password_link(user, purpose):
    link = password_link(user, purpose)
    if purpose == INVITE:
        subject = 'Your ASIMS account: set your password'
        body = (f'Hello {user.full_name},\n\nAn ASIMS account has been created for you as {user.get_role_display()}.\n'
                f'Set your password here:\n{link}\n\nThis link expires in 72 hours and works once. '
                'Then log in with your email address and the password you chose.')
    else:
        subject = 'Reset your ASIMS password'
        body = (f'Hello {user.full_name},\n\nWe received a request to reset your ASIMS password.\n'
                f'Choose a new password here:\n{link}\n\nThis link expires in 1 hour and works once. '
                'If you did not ask for this, ignore this email; your password stays the same.')
    send_mail(subject, body, None, [user.email])
