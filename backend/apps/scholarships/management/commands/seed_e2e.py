"""Fill the throwaway end-to-end database: a department, an open cycle, one account per role and one complete,
submitted application (with its Form 2 scan) waiting at Placement verification.

Runs only against the e2e SQLite file, never the development or production database."""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User
from apps.scholarships.models import ScholarshipCycle
from apps.scholarships.test_submission import fill_complete, pdf

PASSWORD = 'E2e-Test-Passw0rd!'
ACCOUNTS = [
    ('placement@e2e.test', 'Sana Placement', Role.PLACEMENT_OFFICER),
    ('dac@e2e.test', 'Dr Kamran (DAC)', Role.DAC_MEMBER),
    ('director@e2e.test', 'Director Aslam', Role.DIRECTOR),
    ('registrar@e2e.test', 'Registrar Nadia', Role.REGISTRAR),
    ('vc@e2e.test', 'Vice Chancellor Tariq', Role.VICE_CHANCELLOR),
    ('student@e2e.test', 'Ali Khan', Role.STUDENT),
]


class Command(BaseCommand):
    help = 'Seed the end-to-end test database (refuses any other database).'

    def handle(self, **options):
        db = settings.DATABASES['default']
        if db['ENGINE'] != 'django.db.backends.sqlite3' or 'e2e' not in str(db['NAME']):
            raise CommandError('seed_e2e only runs on the end-to-end SQLite database (SQLITE_PATH containing "e2e").')
        cs = Department.objects.create(name='Computer Science', code='CS')
        today = timezone.localdate()
        cycle = ScholarshipCycle.objects.create(name='Fall-26', opens_on=today - timedelta(days=1),
                                                closes_on=today + timedelta(days=30))
        users = {}
        for email, name, role in ACCOUNTS:
            users[role] = User.objects.create_user(
                email=email, password=PASSWORD, full_name=name, role=role, is_email_verified=True,
                department=cs if role in (Role.DAC_MEMBER, Role.STUDENT) else None,
                registration_id='233585' if role == Role.STUDENT else None)

        # The student's application, filled and submitted through the real API (same helper as the backend tests)
        api = APIClient()
        api.force_authenticate(users[Role.STUDENT])
        base = '/api/v1/scholarships/applications/'
        app_id = api.post(base, {'cycle': cycle.pk}, format='json').json()['id']
        fill_complete(api, app_id)
        api.patch(f'{base}{app_id}/sections/undertaking/', {'undertaking_name': 'Ali Khan'}, format='json')
        response = api.post(f'{base}{app_id}/submit/')
        if response.status_code != 200:
            raise CommandError(f'Submitting the seed application failed: {response.content!r}')
        declaration = api.get(f'{base}{app_id}/declarations/').json()[0]
        api.post(f'{base}{app_id}/declarations/{declaration["id"]}/scan/', {'file': pdf('stamp-paper.pdf')},
                 format='multipart')
        self.stdout.write(f'Seeded application {app_id} at Placement verification.')
