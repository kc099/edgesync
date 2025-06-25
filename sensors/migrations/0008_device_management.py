# Generated manually for device management features

from django.db import migrations, models
import django.db.models.deletion
import secrets
import uuid


def generate_tokens_for_existing_devices(apps, schema_editor):
    """Generate tokens for existing devices that don't have them"""
    Device = apps.get_model('sensors', 'Device')
    for device in Device.objects.filter(token__isnull=True):
        device.token = secrets.token_urlsafe(32)
        device.save(update_fields=['token'])


def reverse_tokens(apps, schema_editor):
    """Reverse operation for tokens"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0004_project_dashboardtemplate_project'),
        ('sensors', '0007_auto_20250616_2006'),
    ]

    operations = [
        # Rename device_name to name
        migrations.RenameField(
            model_name='device',
            old_name='device_name',
            new_name='name',
        ),
        
        # Add UUID field
        migrations.AddField(
            model_name='device',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        
        # Add description field
        migrations.AddField(
            model_name='device',
            name='description',
            field=models.TextField(blank=True, help_text='Device description'),
        ),
        
        # Add token field
        migrations.AddField(
            model_name='device',
            name='token',
            field=models.CharField(help_text='Unique authentication token for device', max_length=255, null=True, unique=True),
        ),
        
        # Add creator field (nullable first)
        migrations.AddField(
            model_name='device',
            name='creator',
            field=models.ForeignKey(help_text='Device creator', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='created_devices', to='auth.user'),
        ),
        
        # Add status field
        migrations.AddField(
            model_name='device',
            name='status',
            field=models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('offline', 'Offline'), ('error', 'Error')], default='active', help_text='Device status', max_length=20),
        ),
        
        # Add last_seen field
        migrations.AddField(
            model_name='device',
            name='last_seen',
            field=models.DateTimeField(blank=True, help_text='When device was last seen online', null=True),
        ),
        
        # Add updated_at field
        migrations.AddField(
            model_name='device',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        
        # Update organization field to be non-nullable and add related_name
        migrations.AlterField(
            model_name='device',
            name='organization',
            field=models.ForeignKey(help_text='Organization this device belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='devices', to='user.organization'),
        ),
        
        # Update user field to add related_name for legacy compatibility
        migrations.AlterField(
            model_name='device',
            name='user',
            field=models.ForeignKey(help_text='Legacy device owner', on_delete=django.db.models.deletion.CASCADE, related_name='legacy_devices', to='auth.user'),
        ),
        
        # Make device_id optional (legacy field)
        migrations.AlterField(
            model_name='device',
            name='device_id',
            field=models.CharField(blank=True, help_text='Legacy device identifier', max_length=100),
        ),
        
        # Make tenant_id optional (legacy field)
        migrations.AlterField(
            model_name='device',
            name='tenant_id',
            field=models.CharField(blank=True, help_text='Legacy tenant identifier', max_length=100),
        ),
        
        # Make device_type optional (legacy field)
        migrations.AlterField(
            model_name='device',
            name='device_type',
            field=models.CharField(blank=True, help_text='Type of device', max_length=50),
        ),
        
        # Generate tokens for existing devices
        migrations.RunPython(
            generate_tokens_for_existing_devices,
            reverse_tokens,
        ),
        
        # Make token non-nullable after generating tokens
        migrations.AlterField(
            model_name='device',
            name='token',
            field=models.CharField(help_text='Unique authentication token for device', max_length=255, unique=True),
        ),
        
        # Set creator from user field for existing devices
        migrations.RunSQL(
            "UPDATE devices SET creator_id = user_id WHERE creator_id IS NULL;",
            reverse_sql="UPDATE devices SET creator_id = NULL;",
        ),
        
        # Make creator non-nullable after populating from user field
        migrations.AlterField(
            model_name='device',
            name='creator',
            field=models.ForeignKey(help_text='Device creator', on_delete=django.db.models.deletion.CASCADE, related_name='created_devices', to='auth.user'),
        ),
        
        # Add many-to-many relationship to projects
        migrations.AddField(
            model_name='device',
            name='projects',
            field=models.ManyToManyField(blank=True, help_text='Projects this device is assigned to', related_name='devices', to='user.project'),
        ),
        
        # Add unique constraint for organization + name
        migrations.AddConstraint(
            model_name='device',
            constraint=models.UniqueConstraint(fields=('organization', 'name'), name='unique_device_name_per_org'),
        ),
        
        # Remove old unique constraint on device_id since it's now optional
        migrations.RunSQL(
            "DROP INDEX IF EXISTS sensors_device_device_id_key;",
            reverse_sql="",
        ),
        
        # Add new indexes
        migrations.AddIndex(
            model_name='device',
            index=models.Index(fields=['organization', '-created_at'], name='sensors_device_org_created_idx'),
        ),
        migrations.AddIndex(
            model_name='device',
            index=models.Index(fields=['creator', '-created_at'], name='sensors_device_creator_created_idx'),
        ),
        migrations.AddIndex(
            model_name='device',
            index=models.Index(fields=['uuid'], name='sensors_device_uuid_idx'),
        ),
        migrations.AddIndex(
            model_name='device',
            index=models.Index(fields=['token'], name='sensors_device_token_idx'),
        ),
        migrations.AddIndex(
            model_name='device',
            index=models.Index(fields=['status', 'is_active'], name='sensors_device_status_active_idx'),
        ),
    ] 