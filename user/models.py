from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import hashlib
import base64
import os
import uuid


class UserProfile(models.Model):
    """Extended user profile with subscription and MQTT information"""
    
    SUBSCRIPTION_TYPES = [
        ('free', 'Free'),
        ('freemium', 'Freemium'),
        ('paid', 'Paid'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    subscription_type = models.CharField(max_length=20, choices=SUBSCRIPTION_TYPES, default='free')
    mqtt_username = models.CharField(max_length=100, blank=True, null=True, help_text="Generated MQTT username")
    mqtt_password_set = models.BooleanField(default=False, help_text="Whether user has set MQTT password")
    mqtt_connected = models.BooleanField(default=False, help_text="Whether user is connected to MQTT broker")
    device_limit = models.IntegerField(default=5, help_text="Maximum number of devices allowed")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
    
    def __str__(self):
        return f"{self.user.email} ({self.subscription_type})"
    
    def get_mqtt_username(self):
        """Return MQTT username if set, otherwise None"""
        return self.mqtt_username
    
    def can_add_device(self):
        """Check if user can add more devices based on their subscription"""
        from sensors.models import Device
        current_device_count = Device.objects.filter(user=self.user).count()
        return current_device_count < self.device_limit


class Organization(models.Model):
    """Organization model for multi-tenant support"""
    
    name = models.CharField(max_length=200, help_text="Organization name")
    description = models.TextField(blank=True, help_text="Organization description")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_organizations', help_text="Organization owner/creator")
    slug = models.SlugField(max_length=100, unique=True, help_text="URL-friendly organization identifier")
    is_active = models.BooleanField(default=True, help_text="Whether organization is active")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'organizations'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_admin_count(self):
        """Get number of admin members"""
        return self.members.filter(role='admin').count()
    
    def get_user_count(self):
        """Get number of user members"""
        return self.members.filter(role='user').count()
    
    def get_project_count(self):
        """Get number of projects in this organization"""
        return self.projects.count()


class OrganizationMember(models.Model):
    """Organization membership model"""
    
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('user', 'User'),
    ]
    
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organization_memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    joined_at = models.DateTimeField(default=timezone.now)
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_invitations')
    
    class Meta:
        db_table = 'organization_members'
        unique_together = ['organization', 'user']
        ordering = ['joined_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.organization.name} ({self.role})"


class Project(models.Model):
    """Project model that unifies Flows and DashboardTemplates under an Organization"""
    
    PROJECT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('archived', 'Archived'),
    ]
    
    # Unique shareable identifier
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    name = models.CharField(max_length=200, help_text="Project name")
    description = models.TextField(blank=True, help_text="Project description")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='projects')
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_projects')
    
    # Project status and metadata
    status = models.CharField(max_length=20, choices=PROJECT_STATUS_CHOICES, default='active')
    tags = models.JSONField(default=list, help_text="Project tags for categorization")
    metadata = models.JSONField(default=dict, help_text="Additional project metadata")
    
    # Project settings
    auto_save = models.BooleanField(default=True, help_text="Auto-save flow changes")
    data_retention_days = models.IntegerField(default=30, help_text="Data retention period in days")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'projects'
        ordering = ['-updated_at']
        unique_together = ['organization', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.organization.name})"
    
    def get_flow_count(self):
        """Get number of flows in this project"""
        from flows.models import FlowDiagram
        return FlowDiagram.objects.filter(project=self).count()
    
    def get_dashboard_count(self):
        """Get number of dashboard templates in this project"""
        return self.dashboard_templates.count()


class DashboardTemplate(models.Model):
    """Dashboard template model for organizations"""
    
    # Unique shareable identifier
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    CHART_TYPES = [
        ('time_series', 'Time Series'),
        ('bar_chart', 'Bar Chart'),
        ('gauge', 'Gauge'),
        ('stat_panel', 'Stat Panel'),
        ('pie_chart', 'Pie Chart'),
        ('table', 'Table'),
        ('histogram', 'Histogram'),
        ('xy_chart', 'XY Chart'),
        ('trend_chart', 'Trend Chart'),
    ]
    
    DATASOURCE_TYPES = [
        ('mysql', 'MySQL'),
        ('postgresql', 'PostgreSQL'),
        ('influxdb', 'InfluxDB'),
    ]
    
    name = models.CharField(max_length=200, help_text="Template name")
    description = models.TextField(blank=True, help_text="Template description")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='dashboard_templates')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='dashboard_templates', null=True, blank=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_templates')
    
    # Dashboard configuration
    layout = models.JSONField(default=dict, help_text="Dashboard layout configuration")
    widgets = models.JSONField(default=list, help_text="Dashboard widgets configuration")
    datasources = models.JSONField(default=list, help_text="Connected datasources")
    
    # Template settings
    update_frequency = models.IntegerField(default=30, help_text="Update frequency in seconds")
    connection_timeout = models.IntegerField(default=10, help_text="Database connection timeout in seconds")
    
    # Flow configuration
    flow_config = models.JSONField(default=dict, help_text="Associated flow configuration")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dashboard_templates'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.name} ({self.organization.name})"
    
    def get_admin_count(self):
        """Get number of admin permissions"""
        return self.permissions.filter(permission_type='admin').count()
    
    def get_user_count(self):
        """Get number of user permissions"""
        return self.permissions.filter(permission_type='user').count()


class TemplatePermission(models.Model):
    """Template permission model for sharing templates"""
    
    PERMISSION_TYPES = [
        ('admin', 'Admin'),  # Can edit template, flows, and manage users
        ('user', 'User'),    # Can only view template content
    ]
    
    template = models.ForeignKey(DashboardTemplate, on_delete=models.CASCADE, related_name='permissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='template_permissions')
    permission_type = models.CharField(max_length=10, choices=PERMISSION_TYPES, default='user')
    granted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='granted_permissions')
    granted_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'template_permissions'
        unique_together = ['template', 'user']
        ordering = ['granted_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.template.name} ({self.permission_type})"


class MosquittoUser(models.Model):
    """Model for Mosquitto MQTT users - matches mosquitto_users table"""
    
    username = models.CharField(max_length=100, primary_key=True)
    password = models.TextField(help_text="PBKDF2 hashed password")
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        db_table = 'mosquitto_users'
        managed = False  # Don't let Django manage this table
    
    def __str__(self):
        return self.username
    
    @classmethod
    def create_pbkdf2_password(cls, password):
        """Create PBKDF2 password hash compatible with mosquitto-go-auth"""
        salt = os.urandom(16)
        iterations = 100000
        hash_obj = hashlib.pbkdf2_hmac('sha512', password.encode(), salt, iterations)
        
        salt_b64 = base64.b64encode(salt).decode()
        hash_b64 = base64.b64encode(hash_obj).decode()
        
        return f"PBKDF2$sha512${iterations}${salt_b64}${hash_b64}"


class MosquittoACL(models.Model):
    """Model for Mosquitto ACLs - matches mosquitto_acls table"""
    
    ACCESS_READ = 1
    ACCESS_WRITE = 2
    ACCESS_READWRITE = 3
    ACCESS_SUBSCRIBE = 4
    
    ACCESS_CHOICES = [
        (ACCESS_READ, 'Read'),
        (ACCESS_WRITE, 'Write'),
        (ACCESS_READWRITE, 'Read/Write'),
        (ACCESS_SUBSCRIBE, 'Subscribe'),
    ]
    
    username = models.CharField(max_length=100)
    topic = models.TextField()
    access = models.IntegerField(choices=ACCESS_CHOICES)
    
    class Meta:
        db_table = 'mosquitto_acls'
        managed = False  # Don't let Django manage this table
    
    def __str__(self):
        return f"{self.username} - {self.topic} ({self.get_access_display()})"


class MosquittoSuperuser(models.Model):
    """Model for Mosquitto superusers - matches mosquitto_superusers table"""
    
    username = models.CharField(max_length=100, primary_key=True)
    is_superuser = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'mosquitto_superusers'
        managed = False  # Don't let Django manage this table
    
    def __str__(self):
        return f"{self.username} ({'Super' if self.is_superuser else 'Normal'})"


class DeviceHistory(models.Model):
    """Track device usage and history for users"""
    
    ACTION_TYPES = [
        ('created', 'Device Created'),
        ('updated', 'Device Updated'),
        ('deleted', 'Device Deleted'),
        ('connected', 'Device Connected'),
        ('disconnected', 'Device Disconnected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_history')
    device_id = models.CharField(max_length=100, help_text="Device identifier")
    device_name = models.CharField(max_length=200, help_text="Device name at time of action")
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    details = models.JSONField(blank=True, null=True, help_text="Additional action details")
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'device_history'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['device_id', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.device_name} ({self.action}) at {self.timestamp}"


class UserACL(models.Model):
    """Model for user-based ACLs with topic patterns"""
    
    ACCESS_READ = 1
    ACCESS_WRITE = 2  
    ACCESS_READWRITE = 3
    ACCESS_SUBSCRIBE = 4
    
    ACCESS_CHOICES = [
        (ACCESS_READ, 'Read'),
        (ACCESS_WRITE, 'Write'),
        (ACCESS_READWRITE, 'Read/Write'), 
        (ACCESS_SUBSCRIBE, 'Subscribe'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    topic_pattern = models.TextField(help_text="MQTT topic pattern (e.g., iot/tenant_001/+/+)")
    access_type = models.IntegerField(choices=ACCESS_CHOICES)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'user_acls'
        unique_together = ['user', 'topic_pattern', 'access_type']
    
    def __str__(self):
        return f"{self.user.username} - {self.topic_pattern} ({self.get_access_type_display()})"