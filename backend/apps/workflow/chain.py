"""Running a workflow on a case: one place that locks the record, checks the action, saves the new stage with its
history and records it in the audit log, shared by the scholarship and internship chains.

What differs between chains is passed in as hooks:
- clean(transition, **options) -> dict: checks extra values an action takes (e.g. a scholarship percentage) and
  returns them; they are saved on the history row and in the audit entry.
- checks: {(action, source stage): check(obj)} conditions that raise ValidationError.
- update(obj, transition, user, remarks, values) -> list: sets the chain's own fields, returns their names.
- after: {(action, source stage): after(obj, user)} follow-up work in the same transaction.
- on_moved(obj, change, user): who is told about the move."""
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit.log import record
from apps.audit.models import AuditAction


def _no_options(transition):
    return {}


def _no_fields(obj, transition, user, remarks, values):
    return []


class Chain:
    def __init__(self, workflow, model, history, case_field, *, related=(), clean=_no_options, checks=None,
                 update=_no_fields, after=None, on_moved=None):
        self.workflow = workflow
        self.model = model
        self.history = history
        self.case_field = case_field
        self.related = related
        self.clean = clean
        self.checks = checks or {}
        self.update = update
        self.after = after or {}
        self.on_moved = on_moved

    def perform(self, pk, action, user, *, remarks='', request=None, **options):
        """Take `action` on the case as `user` and record it. The row is locked first, so when two people act at
        once the second gets a WorkflowError ('stage_conflict') instead of moving the case twice."""
        with transaction.atomic():
            obj = self.model.objects.select_for_update(of=('self',)).select_related(*self.related).get(pk=pk)
            transition = self.workflow.find(user, obj, obj.status, action)
            remarks = (remarks or '').strip()
            if transition.remarks_required and not remarks:
                raise ValidationError({'remarks': 'Remarks are required for this action, so the reason is on record.'})
            values = self.clean(transition, **options)
            key = (transition.action, transition.source)
            if check := self.checks.get(key):
                check(obj)

            change = self.history.objects.create(
                **{self.case_field: obj}, from_status=transition.source, to_status=transition.target,
                action=transition.action, remarks=remarks, changed_by=user, role=user.role, **values)
            obj.status = transition.target
            obj.save(update_fields=['status', 'updated_at', *self.update(obj, transition, user, remarks, values)])
            if after := self.after.get(key):
                after(obj, user)
            if self.on_moved:
                self.on_moved(obj, change, user)
            record(AuditAction.WORKFLOW_ACTION, request=request, actor=user, target=obj, action=transition.action,
                   from_status=transition.source, to_status=transition.target, remarks=remarks, **values)
        return obj
