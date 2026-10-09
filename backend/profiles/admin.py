from django.contrib import admin
from .models import UserProfile, DriverVerification

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'active_role', 'onboarding_status', 'first_name', 'last_name', 'created_at']
    list_filter = ['active_role', 'onboarding_status', 'gender']
    search_fields = ['user__phone_number', 'first_name', 'last_name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Profile', {
            'fields': ('active_role', 'first_name', 'last_name', 'age', 'gender')
        }),
        ('Onboarding', {
            'fields': ('onboarding_status',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(DriverVerification)
class DriverVerificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'dl_verification_status', 'dl_number_display', 'attempt_count', 'dl_submitted_at']
    list_filter = ['dl_verification_status']
    search_fields = ['user__phone_number', 'dl_verification_ref']
    readonly_fields = ['dl_number', 'dl_number_display', 'dl_submitted_at', 'dl_verified_at', 'created_at', 'updated_at']

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('DL Information', {
            'fields': ('dl_number', 'dl_number_display', 'dl_verification_ref')
        }),
        ('Verification', {
            'fields': ('dl_verification_status', 'dl_rejection_reason', 'attempt_count')
        }),
        ('Timestamps', {
            'fields': ('dl_submitted_at', 'dl_verified_at', 'created_at', 'updated_at')
        }),
    )
