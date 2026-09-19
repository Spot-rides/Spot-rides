#!/usr/bin/env python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

try:
    from accounts.serializers import OtpVerifySerializer
    print("Import successful")
    s = OtpVerifySerializer()
    print(f"Fields defined: {list(s.fields.keys())}")
    print(f"Field details:")
    for name, field in s.fields.items():
        print(f"  {name}: {field.__class__.__name__}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
