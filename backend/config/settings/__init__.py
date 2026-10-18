"""
Settings package — auto-selects environment from DJANGO_ENV.

    DJANGO_ENV=production  → config.settings.production
    DJANGO_ENV=development (default) → config.settings.development

You may also point DJANGO_SETTINGS_MODULE directly at the submodule:
    config.settings.development
    config.settings.production
"""
import os

_env = os.environ.get('DJANGO_ENV', 'development')
if _env == 'production':
    from .production import *
else:
    from .development import *
