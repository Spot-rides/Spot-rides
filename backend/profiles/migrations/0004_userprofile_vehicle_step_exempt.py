from django.db import migrations, models


def mark_grandfathered_drivers(apps, schema_editor):
    """Mark drivers who are COMPLETE, have a DriverVerification, and no active Vehicle row.

    Idempotent: only touches rows still False. Passengers who never went through the driver
    path have no DriverVerification and are not marked.
    """
    UserProfile = apps.get_model('profiles', 'UserProfile')
    Vehicle = apps.get_model('profiles', 'Vehicle')
    DriverVerification = apps.get_model('profiles', 'DriverVerification')

    has_dl = DriverVerification.objects.values('user_id')
    has_vehicle = Vehicle.objects.filter(is_active=True).values('user_id')
    (UserProfile.objects
        .filter(onboarding_status='complete', vehicle_step_exempt=False, user_id__in=has_dl)
        .exclude(user_id__in=has_vehicle)
        .update(vehicle_step_exempt=True))


def unmark(apps, schema_editor):
    # The column is dropped on reverse; nothing to undo explicitly.
    UserProfile = apps.get_model('profiles', 'UserProfile')
    UserProfile.objects.filter(vehicle_step_exempt=True).update(vehicle_step_exempt=False)


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0003_vehicle_rc_verification'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='vehicle_step_exempt',
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text='Driver grandfathered from before the vehicle step existed (FR-43). Set ONLY by the data migration; never set by application code or admin.',
            ),
        ),
        migrations.RunPython(mark_grandfathered_drivers, unmark),
    ]
