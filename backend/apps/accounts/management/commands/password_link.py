"""Print a fresh set-password link for an account, for testing without a mail server.

    python manage.py password_link student@asims.test            # reset link, valid 1 hour
    python manage.py password_link po@au.edu.pk --invite        # invitation link, valid 72 hours"""
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.accounts.passwords import INVITE, RESET, password_link


class Command(BaseCommand):
    help = 'Print a one-time link to set the password of the account with this email.'

    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument('--invite', action='store_true', help='An invitation link (72 hours) instead of a reset.')

    def handle(self, email, invite, **options):
        user = User.objects.filter(email=email.lower(), is_active=True).first()
        if user is None:
            raise CommandError(f'No active account with the email {email}.')
        self.stdout.write(password_link(user, INVITE if invite else RESET))
