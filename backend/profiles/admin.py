from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.db.models import Count, IntegerField, OuterRef, Subquery
from django.db.models.functions import Coalesce

from core.exceptions import ApiError
from .models import UserProfile, DriverVerification, Vehicle

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'active_role', 'onboarding_status', 'first_name', 'last_name', 'created_at']
    list_filter = ['active_role', 'onboarding_status', 'gender']
    search_fields = ['user__phone_number', 'first_name', 'last_name']
    readonly_fields = ['vehicle_step_exempt', 'created_at', 'updated_at']
    # State-machine fields: only superusers may edit them by hand (F-11).
    _state_fields = ['onboarding_status', 'active_role']

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Profile', {
            'fields': ('active_role', 'first_name', 'last_name', 'age', 'gender')
        }),
        ('Onboarding', {
            'fields': ('onboarding_status', 'vehicle_step_exempt')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly += self._state_fields
            if obj is not None:
                readonly.append('user')  # identity key: never re-point a profile
        return readonly


@admin.register(DriverVerification)
class DriverVerificationAdmin(admin.ModelAdmin):
    """DL verification records. Rows are created and moved only by the DL service.

    The encrypted ``dl_number`` is never shown or editable here. Every state field is read-only
    for non-superusers.
    """

    list_display = ['user', 'dl_verification_status', 'dl_number_display', 'attempt_count', 'dl_submitted_at']
    list_filter = ['dl_verification_status']
    search_fields = ['user__phone_number', 'dl_verification_ref']
    exclude = ['dl_number']
    readonly_fields = ['dl_number_display', 'dl_submitted_at', 'dl_verified_at', 'created_at', 'updated_at']
    _state_fields = [
        'dl_verification_status', 'dl_verification_ref', 'attempt_count', 'dl_rejection_reason',
    ]

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('DL Information', {
            'fields': ('dl_number_display', 'dl_verification_ref')
        }),
        ('Verification', {
            'fields': ('dl_verification_status', 'dl_rejection_reason', 'attempt_count')
        }),
        ('Timestamps', {
            'fields': ('dl_submitted_at', 'dl_verified_at', 'created_at', 'updated_at')
        }),
    )

    def has_add_permission(self, request):
        # Rows are created by the DL submission service (it encrypts the DL number); an admin
        # form cannot, and must not, supply one.
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly += self._state_fields
            if obj is not None:
                readonly.append('user')
        return readonly




class RCReviewActionForm(ActionForm):
    rc_reject_reason = forms.CharField(
        required=False,
        max_length=500,
        label='Rejection reason',
        help_text='Used by "Reject RC". Shown to the driver: do not include personal data or the owner name.',
    )


class NeedsReviewFilter(admin.SimpleListFilter):
    title = 'needs review'
    parameter_name = 'needs_review'

    def lookups(self, request, model_admin):
        return [('1', 'Pending review')]

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(rc_verification_status=Vehicle.RC_PENDING)
        return queryset


class DuplicateRegistrationFilter(admin.SimpleListFilter):
    title = 'duplicate registration'
    parameter_name = 'duplicate_reg'

    def lookups(self, request, model_admin):
        return [('1', 'Shared with other drivers')]

    def queryset(self, request, queryset):
        if self.value() == '1':
            return queryset.filter(_other_drivers__gt=0)
        return queryset


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    """RC review queue. State changes happen only through the actions below."""

    list_display = [
        'registration_number', 'user_phone', 'vehicle_type', 'rc_verification_status',
        'rc_name_match', 'rc_attempt_count', 'rc_submitted_at', 'other_drivers_with_same_reg',
    ]
    list_filter = [
        'rc_verification_status', 'rc_name_match', NeedsReviewFilter, DuplicateRegistrationFilter, 'is_active',
    ]
    search_fields = ['user__phone_number', 'registration_number']
    list_select_related = ['user']
    ordering = ['rc_submitted_at']
    action_form = RCReviewActionForm
    actions = ['approve_rc', 'reject_rc', 'reset_rc_attempts']

    fieldsets = (
        ('Vehicle', {'fields': ('user', 'registration_number', 'vehicle_type', 'is_active')}),
        ('RC verification', {'fields': (
            'rc_verification_status', 'rc_name_match', 'rc_attempt_count', 'rc_verification_ref',
            'rc_submitted_at', 'rc_verified_at', 'rc_rejection_reason',
        )}),
        ('Provider data (staff only)', {'fields': (
            'rc_owner_name', 'rc_vehicle_class', 'rc_fuel_type',
            'rc_fitness_valid_upto', 'rc_insurance_valid_upto',
        )}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        others = (
            Vehicle.objects.filter(registration_number=OuterRef('registration_number'))
            .exclude(user=OuterRef('user'))
            .order_by()
            .values('registration_number')
            .annotate(n=Count('user', distinct=True))
            .values('n')
        )
        return super().get_queryset(request).annotate(
            _other_drivers=Coalesce(Subquery(others, output_field=IntegerField()), 0)
        )

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in Vehicle._meta.fields]

    def get_fieldsets(self, request, obj=None):
        """The third-party owner name is shown only to holders of profiles.review_rc (F-07)."""
        fieldsets = super().get_fieldsets(request, obj)
        if self.has_review_rc_permission(request):
            return fieldsets
        return [
            (name, {**options, 'fields': tuple(f for f in options['fields'] if f != 'rc_owner_name')})
            for name, options in fieldsets
        ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_review_rc_permission(self, request):
        return request.user.has_perm('profiles.review_rc')

    @admin.display(description='User', ordering='user__phone_number')
    def user_phone(self, obj):
        return obj.user.phone_number

    @admin.display(description='Other drivers, same reg.', ordering='_other_drivers')
    def other_drivers_with_same_reg(self, obj):
        return obj._other_drivers

    def _run(self, request, queryset, label, call):
        done = 0
        for vehicle in queryset:
            try:
                call(vehicle)
            except ApiError as exc:
                self.message_user(request, f'Vehicle {vehicle.pk}: {exc.detail}', messages.ERROR)
                continue
            self.log_change(request, vehicle, f'RC review: {label}')
            done += 1
        if done:
            self.message_user(request, f'{label}: {done} vehicle(s).', messages.SUCCESS)

    @admin.action(description='Approve RC (review)', permissions=['review_rc'])
    def approve_rc(self, request, queryset):
        from profiles.services import rc_verification

        self._run(request, queryset, 'approved', lambda v: rc_verification.resolve_rc_review(
            v.pk, approve=True, reason=None, staff_user=request.user))

    @admin.action(description='Reject RC (review) - enter a reason', permissions=['review_rc'])
    def reject_rc(self, request, queryset):
        from profiles.services import rc_verification

        reason = (request.POST.get('rc_reject_reason') or '').strip()
        if not reason:
            self.message_user(request, 'Enter a rejection reason; nothing was changed.', messages.ERROR)
            return
        self._run(request, queryset, 'rejected', lambda v: rc_verification.resolve_rc_review(
            v.pk, approve=False, reason=reason, staff_user=request.user))

    @admin.action(description='Reset RC attempts', permissions=['review_rc'])
    def reset_rc_attempts(self, request, queryset):
        from profiles.services import rc_verification

        self._run(request, queryset, 'attempts reset', lambda v: rc_verification.reset_rc_attempts(
            v.pk, staff_user=request.user))
