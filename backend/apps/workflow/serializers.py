from rest_framework import serializers

from apps.accounts.models import Role


class StatusChangeSerializer(serializers.ModelSerializer):
    """One row of a case's history. Each chain sets Meta.model to its history model and may add fields."""
    changed_by = serializers.CharField(source='changed_by.full_name', read_only=True)
    changed_by_role = serializers.SerializerMethodField()
    from_label = serializers.CharField(source='get_from_status_display', read_only=True)
    to_label = serializers.CharField(source='get_to_status_display', read_only=True)

    class Meta:
        fields = ['from_status', 'from_label', 'to_status', 'to_label', 'action', 'remarks', 'changed_by',
                  'changed_by_role', 'changed_at']

    def get_changed_by_role(self, obj) -> str:
        # The role held when acting; a person's role may change later
        return Role(obj.role).label if obj.role in Role.values else obj.role
