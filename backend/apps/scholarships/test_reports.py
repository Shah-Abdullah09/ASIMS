"""Scholarship reports: the management summary and the CSV export."""
import csv
import io
from datetime import date

import pytest

from apps.accounts.models import Role

from .models import Application, FeeAdjustment, ScholarshipCycle
from .test_review import client_for, cs, cycle, ee, make_user, submitted_application, temp_media  # noqa: F401

SUMMARY, EXPORT = '/api/v1/reports/scholarships/', '/api/v1/reports/scholarships.csv'


@pytest.fixture
def cases(cycle, cs, ee):
    """Fall-26: Ali (CS, completed 60%), Sara (CS, rejected), Bilal (EE, at DAC review); Spring-27: Zara (EE,
    approved 40%); plus a draft that never counts."""
    finance = make_user('finance@au.edu.pk', role=Role.FINANCE_OFFICER)
    _, ali = submitted_application(cycle, cs, 'ali@gmail.com', 'Ali Khan', '233585', '36302-1234567-1')
    _, sara = submitted_application(cycle, cs, 'sara@gmail.com', '=Sara Ahmed', '2335901', '36302-7654321-2')
    _, bilal = submitted_application(cycle, ee, 'bilal@gmail.com', 'Bilal Raza', '24400012', '36302-1111222-3')
    spring = ScholarshipCycle.objects.create(name='Spring-27', opens_on=cycle.opens_on, closes_on=cycle.closes_on)
    _, zara = submitted_application(spring, ee, 'zara@gmail.com', 'Zara Ali', '24400013', '36302-1111222-4')
    Application.objects.filter(pk=ali).update(status='completed', scholarship_percentage=60)
    Application.objects.filter(pk=sara).update(status='rejected')
    Application.objects.filter(pk=bilal).update(status='dac_review')
    Application.objects.filter(pk=zara).update(status='awaiting_fee_adjustment', scholarship_percentage=40)
    adj = FeeAdjustment(application_id=ali, semester_fee=150000, percentage=60, voucher_number='CH-1',
                        adjusted_on=date(2026, 11, 1), recorded_by=finance)
    adj.calculate()
    adj.save()
    Application.objects.create(cycle=cycle, student=make_user('draft@gmail.com', dept=cs))
    return {'fall': cycle.pk, 'spring': spring.pk, 'ali': ali}


def test_summary_counts_and_totals(cases):
    director = client_for(make_user('director@au.edu.pk', role=Role.DIRECTOR))
    everything = director.get(SUMMARY).json()
    assert (everything['submitted'], everything['approved'], everything['rejected'], everything['completed'],
            everything['in_progress']) == (4, 2, 1, 1, 1)
    assert everything['average_percentage'] == 50.0 and everything['total_scholarship_amount'] == 90000
    fall = director.get(f"{SUMMARY}?cycle={cases['fall']}").json()
    assert fall['cycle']['name'] == 'Fall-26' and fall['submitted'] == 3 and fall['approved'] == 1
    stages = {row['stage']: row['count'] for row in fall['by_stage']}
    assert stages['completed'] == 1 and stages['rejected'] == 1 and stages['dac_review'] == 1 and 'draft' not in stages
    departments = {row['department']: row for row in fall['by_department']}
    assert departments['Computer Science'] == {'department': 'Computer Science', 'submitted': 2, 'approved': 1,
                                               'rejected': 1}


def test_csv_export(cases):
    officer = client_for(make_user('po@au.edu.pk', role=Role.PLACEMENT_OFFICER))
    response = officer.get(f"{EXPORT}?cycle={cases['fall']}")
    assert response.status_code == 200 and response['Content-Type'].startswith('text/csv')
    assert 'asims-scholarships-Fall-26.csv' in response['Content-Disposition']
    rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
    assert rows[0][0] == 'Application' and len(rows) == 4  # header + 3 Fall-26 cases, no draft
    ali = next(r for r in rows if r[0] == str(cases['ali']))
    assert ali[6] == 'Completed' and ali[8:12] == ['60', '150000', '90000', '60000']
    sara = next(r for r in rows if r[6] == 'Rejected')
    assert sara[1] == "'=Sara Ahmed"  # a formula-looking name is kept as text


@pytest.mark.parametrize('role,summary_code,export_code', [
    (Role.ADMINISTRATOR, 200, 200), (Role.FINANCE_OFFICER, 200, 403), (Role.VICE_CHANCELLOR, 200, 403),
    (Role.DAC_MEMBER, 403, 403), (Role.STUDENT, 403, 403)])
def test_who_sees_reports(db, role, summary_code, export_code):
    client = client_for(make_user(f'{role}@au.edu.pk', role=role))
    assert client.get(SUMMARY).status_code == summary_code
    assert client.get(EXPORT).status_code == export_code
