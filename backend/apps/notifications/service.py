"""Sending notifications: always in the app, and by email to people who have email notifications switched on.

Emails go out after the database transaction commits, so a rolled-back action never emails anyone, and a mail
server problem is logged without undoing the action."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from .models import Notification

log = logging.getLogger(__name__)


def _email(user, title, body, link):
    url = f'{settings.FRONTEND_URL}{link}' if link else settings.FRONTEND_URL
    try:
        send_mail(f'ASIMS: {title}', f'Dear {user.full_name},\n\n{body}\n\nOpen ASIMS: {url}', None, [user.email])
    except Exception:
        log.exception('Could not email %s about "%s"', user.email, title)


def notify(users, title, body='', link='', email=True):
    """Notify each active user in the app, and by email when `email` is set and they have not switched it off."""
    sent = []
    for user in users:
        if not user.is_active:
            continue
        sent.append(Notification.objects.create(recipient=user, title=title[:200], body=body, link=link))
        if email and user.email_notifications:
            transaction.on_commit(lambda u=user: _email(u, title, body, link))
    return sent
