from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'recipient', 'title', 'read_at']
    list_filter = ['read_at']
    search_fields = ['recipient__email', 'title']
    list_select_related = ['recipient']
