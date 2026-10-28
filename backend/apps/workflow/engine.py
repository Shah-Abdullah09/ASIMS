"""A small state machine shared by the scholarship chain now and the internship chain later.

A workflow is a list of transitions. Each transition names an action, the stage it starts from, the stage
it leads to and the roles allowed to take it. The caller locks the record, asks the workflow for the
transition and saves the new stage with its history in the same database transaction, so two people
acting on the same case at once cannot both move it."""
from collections.abc import Callable
from dataclasses import dataclass


class WorkflowError(Exception):
    """An action that cannot be taken now. `message` is safe to show to the user.

    code: 'unknown_action', 'forbidden' (wrong role or out of scope) or 'stage_conflict'
    (the case is not, or no longer, at the stage the action starts from)."""

    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class Transition:
    action: str
    label: str
    source: str
    target: str
    roles: tuple
    remarks_required: bool = False
    # Extra limit on who may act, e.g. a DAC member only for their own department: (user, obj) -> bool
    scope: Callable | None = None

    def allows(self, user, obj):
        return user.role in self.roles and (self.scope is None or self.scope(user, obj))


class Workflow:
    def __init__(self, transitions, stage_labels):
        self.transitions = list(transitions)
        self.stage_labels = dict(stage_labels)
        keys = [(t.action, t.source) for t in self.transitions]
        if len(keys) != len(set(keys)):
            raise ValueError('Each action may start from a stage only once.')
        unknown = {s for t in self.transitions for s in (t.source, t.target)} - set(self.stage_labels)
        if unknown:
            raise ValueError(f'Transitions use stages without a label: {sorted(unknown)}')

    def label(self, stage):
        return self.stage_labels.get(stage, stage)

    def from_stage(self, stage):
        return [t for t in self.transitions if t.source == stage]

    def available(self, user, obj, stage):
        """The actions this user may take on obj, which is at `stage`."""
        return [t for t in self.from_stage(stage) if t.allows(user, obj)]

    def acting_roles(self, stage):
        """Roles that act at this stage (empty for a final stage)."""
        return {role for t in self.from_stage(stage) for role in t.roles}

    def is_final(self, stage):
        return not self.from_stage(stage)

    def find(self, user, obj, stage, action):
        """The transition for `action` from `stage`, or WorkflowError explaining why it is not possible."""
        candidates = [t for t in self.transitions if t.action == action]
        if not candidates:
            raise WorkflowError(f'Unknown action "{action}".', 'unknown_action')
        transition = next((t for t in candidates if t.source == stage), None)
        if transition is None:
            raise WorkflowError(f'This case is at "{self.label(stage)}", so "{candidates[0].label}" is not '
                                'possible. It may have just been moved by someone else; reload the page.',
                                'stage_conflict')
        if not transition.allows(user, obj):
            raise WorkflowError('You are not allowed to take this action on this case.', 'forbidden')
        return transition
