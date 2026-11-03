"""Scholarship reports: a summary for management and a CSV export of the applications. Drafts are left out."""
import csv
import io

from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import has_role

from .choices import ApplicationStatus as S
from .models import Application, FeeAdjustment, ScholarshipCycle

SUMMARY_ROLES = (Role.PLACEMENT_OFFICER, Role.ADMINISTRATOR, Role.DIRECTOR, Role.REGISTRAR, Role.VICE_CHANCELLOR,
                 Role.FINANCE_OFFICER)
EXPORT_ROLES = (Role.PLACEMENT_OFFICER, Role.ADMINISTRATOR)  # the export holds personal data
APPROVED = (S.AWAITING_FEE_ADJUSTMENT, S.COMPLETED)
CLOSED = (*APPROVED, S.REJECTED)


def submitted(cycle_id=None):
    qs = Application.objects.exclude(status=S.DRAFT)
    return qs.filter(cycle_id=cycle_id) if cycle_id else qs


def cycle_param(request):
    value = request.query_params.get('cycle')
    return int(value) if value and value.isdigit() else None


def summary(cycle_id=None):
    apps = submitted(cycle_id)
    counts = dict(apps.values_list('status').annotate(n=Count('pk')))
    by_department = (apps.values('student__department__name')
                     .annotate(submitted=Count('pk'), approved=Count('pk', filter=Q(status__in=APPROVED)),
                               rejected=Count('pk', filter=Q(status=S.REJECTED)))
                     .order_by('student__department__name'))
    approved = apps.filter(status__in=APPROVED)
    fees = FeeAdjustment.objects.filter(application__in=apps)
    cycle = ScholarshipCycle.objects.filter(pk=cycle_id).values('id', 'name').first() if cycle_id else None
    return {
        'cycle': cycle,
        'generated_at': timezone.now(),
        'submitted': apps.count(),
        'in_progress': apps.exclude(status__in=CLOSED).count(),
        'approved': approved.count(),
        'rejected': counts.get(S.REJECTED, 0),
        'completed': counts.get(S.COMPLETED, 0),
        'by_stage': [{'stage': value, 'label': label, 'count': counts.get(value, 0)}
                     for value, label in S.choices if value != S.DRAFT],
        'by_department': [{'department': row['student__department__name'] or 'No department',
                           'submitted': row['submitted'], 'approved': row['approved'], 'rejected': row['rejected']}
                          for row in by_department],
        'average_percentage': round(approved.aggregate(v=Avg('scholarship_percentage'))['v'] or 0, 1),
        'total_scholarship_amount': fees.aggregate(v=Sum('scholarship_amount'))['v'] or 0,
        'total_semester_fees': fees.aggregate(v=Sum('semester_fee'))['v'] or 0,
    }


class ScholarshipSummaryView(APIView):
    """Counts and totals for one cycle (?cycle=) or all cycles."""

    permission_classes = [has_role(*SUMMARY_ROLES)]

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(summary(cycle_param(request)))


COLUMNS = ['Application', 'Applicant', 'Registration ID', 'Email', 'Department', 'Cycle', 'Stage', 'Submitted on',
           'Scholarship %', 'Semester fee (Rs)', 'Scholarship amount (Rs)', 'Fee payable (Rs)', 'Voucher']


def _safe(value):
    """Spreadsheet programs run cells starting with = + - @ as formulas; prefix them so they stay text."""
    text = '' if value is None else str(value)
    return f"'{text}" if text[:1] in ('=', '+', '-', '@') else text


class ScholarshipExportView(APIView):
    """The submitted applications as a CSV file (opens in Excel), for one cycle (?cycle=) or all."""

    permission_classes = [has_role(*EXPORT_ROLES)]

    @extend_schema(responses={(200, 'text/csv'): OpenApiTypes.STR})
    def get(self, request):
        cycle_id = cycle_param(request)
        apps = (submitted(cycle_id).select_related('cycle', 'student__department', 'fee_adjustment')
                .order_by('cycle__opens_on', 'pk'))
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(COLUMNS)
        for app in apps:
            adj = getattr(app, 'fee_adjustment', None)
            writer.writerow([_safe(v) for v in (
                app.pk, app.applicant_name, app.registration_id, app.email or app.student.email,
                app.student.department.name if app.student.department else '', app.cycle.name,
                app.get_status_display(), timezone.localtime(app.submitted_at).date() if app.submitted_at else '',
                app.scholarship_percentage if app.status in APPROVED else '',
                adj.semester_fee if adj else '', adj.scholarship_amount if adj else '', adj.fee_payable if adj else '',
                adj.voucher_number if adj else '')])
        name = f"asims-scholarships-{apps.first().cycle.name if cycle_id and apps.exists() else 'all'}.csv"
        response = HttpResponse('﻿' + buffer.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{name}"'
        response['Cache-Control'] = 'private, no-store'
        return response
