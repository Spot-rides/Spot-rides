"""URL routing for the profiles app (FEAT-002 onboarding endpoints).

All endpoints are prefixed with /api/ at the project level.
"""

from django.urls import path
from profiles import views

urlpatterns = [
    # Onboarding endpoints
    path('onboarding/status/', views.OnboardingStatusView.as_view(), name='onboarding-status'),
    path('onboarding/role/', views.RoleSelectView.as_view(), name='onboarding-role'),
    path('onboarding/profile/', views.ProfileSubmitView.as_view(), name='onboarding-profile'),
    path('onboarding/driver/dl/', views.DLSubmitView.as_view(), name='onboarding-dl-submit'),
    path('onboarding/driver/dl/status/', views.DLStatusView.as_view(), name='onboarding-dl-status'),
    path('onboarding/driver/dl/webhook/', views.DLWebhookView.as_view(), name='onboarding-dl-webhook'),

    # Profile management endpoints
    path('profile/role/', views.RoleSwitchView.as_view(), name='profile-role-switch'),
]
