from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import hashlib
import base64
import os


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
    
    READ = 1
    WRITE = 2
    READWRITE = 3
    SUBSCRIBE = 4
    
    RW_CHOICES = [
        (READ, 'Read'),
        (WRITE, 'Write'), 
        (READWRITE, 'Read/Write'),
        (SUBSCRIBE, 'Subscribe'),
    ]
    
    username = models.CharField(max_length=100)
    topic = models.TextField(help_text="MQTT topic pattern")
    rw = models.IntegerField(choices=RW_CHOICES, help_text="Read/Write permissions")
    
    class Meta:
        db_table = 'mosquitto_acls'
        managed = False  # Don't let Django manage this table
        unique_together = ['username', 'topic', 'rw']
    
    def __str__(self):
        return f"{self.username} - {self.topic} ({self.get_rw_display()})"


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