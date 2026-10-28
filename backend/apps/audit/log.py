from .models import AuditLog


def client_ip(request):
    """The connecting address. X-Forwarded-For is ignored until a trusted proxy is set up at deployment."""
    return request.META.get('REMOTE_ADDR') if request is not None else None


def record(action, /, *, request=None, actor=None, target=None, **details):
    """Add one audit entry. `actor` defaults to the logged-in user of `request`; `target` is a model instance."""
    if actor is None and request is not None and request.user.is_authenticated:
        actor = request.user
    return AuditLog.objects.create(
        actor=actor,
        actor_role=getattr(actor, 'role', '') or '',
        action=action,
        target_type=target._meta.label_lower if target is not None else '',
        target_id=str(target.pk) if target is not None else '',
        details=details,
        ip_address=client_ip(request),
    )
