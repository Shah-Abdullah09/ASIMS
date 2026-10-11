from rest_framework.permissions import BasePermission


def has_role(*roles):
    """Build a DRF permission class that only lets users with one of `roles` through."""

    class HasRole(BasePermission):
        message = 'Your role is not allowed to perform this action.'

        def has_permission(self, request, view):
            user = request.user
            return bool(user and user.is_authenticated and user.role in roles)

    HasRole.__name__ = 'HasRole_' + '_'.join(roles)
    return HasRole
