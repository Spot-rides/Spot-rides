"""URL routes for the ``accounts`` app.

Implements PLAN-001 TASK-021 / ARCH-001 §URL Routing Changes. Included
under ``/api/auth/`` from ``backend/config/urls.py``. Named routes are
stable — tests and reverse() callers rely on them.
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LogoutView, MeView, OtpRequestView, OtpVerifyView


urlpatterns = [
    path('otp/request/', OtpRequestView.as_view(), name='otp-request'),
    path('otp/verify/', OtpVerifyView.as_view(), name='otp-verify'),
    path('token/refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
]
