"""Minimal admin registrations for ops visibility (TASK-008, NFR-PRIV-01).

- ``UserAdmin`` is staff-restricted (default Django admin gating) and shows
  the phone number.
- ``OtpCodeAdmin`` is read-only: no create/edit; raw codes are never stored,
  only the ``code_hash`` is displayed.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import OtpCode, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ('phone_number',)
    list_display = ('id', 'phone_number', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('phone_number',)
    list_filter = ('is_staff', 'is_active', 'is_superuser')

    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password1', 'password2'),
        }),
    )


@admin.register(OtpCode)
class OtpCodeAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'phone_number', 'created_at', 'expires_at',
        'consumed_at', 'attempts', 'invalidated',
    )
    list_filter = ('invalidated',)
    search_fields = ('phone_number', 'request_id')
    readonly_fields = (
        'phone_number', 'code_hash', 'created_at', 'expires_at',
        'consumed_at', 'attempts', 'invalidated', 'request_ip', 'request_id',
    )
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Deletion is reserved for the ``purge_expired_otps`` command (COMP-013).
        return False
