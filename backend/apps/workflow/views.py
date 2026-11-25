from rest_framework import status
from rest_framework.response import Response

from .engine import WorkflowError

ERROR_STATUS = {'unknown_action': status.HTTP_400_BAD_REQUEST, 'forbidden': status.HTTP_403_FORBIDDEN,
                'stage_conflict': status.HTTP_409_CONFLICT}


def run_action(chain, pk, action, user, request, **options):
    """Take a workflow action through `chain`; returns an error Response, or None when it succeeded."""
    try:
        chain.perform(pk, action, user, request=request, **options)
    except WorkflowError as exc:
        return Response({'detail': exc.message, 'code': exc.code}, status=ERROR_STATUS[exc.code])
    return None
