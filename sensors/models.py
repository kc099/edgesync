from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json
import uuid
import secrets

class SensorData(models.Model):
    """Model to store sensor data received from ESP32 devices"""
    
    device_id = models.CharField(max_length=100, help_text="Unique identifier for the ESP32 device")
    sensor_type = models.CharField(max_length=50, help_text="Type of sensor (e.g., temperature, humidity, pressure)")
    value = models.FloatField(help_text="Sensor reading value")
    unit = models.CharField(max_length=20, blank=True, help_text="Unit of measurement")
    timestamp = models.DateTimeField(default=timezone.now, help_text="When the data was received")
    raw_data = models.JSONField(blank=True, null=True, help_text="Original JSON data from ESP32")
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device_id', '-timestamp']),
            models.Index(fields=['sensor_type', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.device_id} - {self.sensor_type}: {self.value} {self.unit} at {self.timestamp}"
    
    @classmethod
    def create_from_esp32_data(cls, data):
        """Create SensorData instance from ESP32 JSON data"""
        try:
            if isinstance(data, str):
                data = json.loads(data)
            
            return cls.objects.create(
                device_id=data.get('device_id', 'unknown'),
                sensor_type=data.get('sensor_type', 'unknown'),
                value=float(data.get('value', 0)),
                unit=data.get('unit', ''),
                raw_data=data
            )
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            raise ValueError(f"Invalid sensor data format: {e}")


class Device(models.Model):
    """Model to store IoT device information with project assignment capabilities"""
    
    DEVICE_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('offline', 'Offline'),
        ('error', 'Error'),
    ]
    
    # Unique shareable identifier
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Basic device information
    name = models.CharField(max_length=200, help_text="Human readable device name")
    description = models.TextField(blank=True, help_text="Device description")
    
    # Authentication token for device API access
    token = models.CharField(max_length=255, unique=True, help_text="Unique authentication token for device")
    
    # Relationships
    organization = models.ForeignKey(
        'user.Organization', 
        on_delete=models.CASCADE, 
        related_name='devices',
        help_text="Organization this device belongs to"
    )
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_devices', help_text="Device creator")
    projects = models.ManyToManyField('user.Project', blank=True, related_name='devices', help_text="Projects this device is assigned to")
    
    # Device status and metadata
    status = models.CharField(max_length=20, choices=DEVICE_STATUS_CHOICES, default='active')
    last_seen = models.DateTimeField(null=True, blank=True, help_text="When device was last seen online")
    
    # Legacy fields for backward compatibility
    device_id = models.CharField(max_length=100, blank=True, help_text="Legacy device identifier")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='legacy_devices', help_text="Legacy device owner")
    tenant_id = models.CharField(max_length=100, blank=True, help_text="Legacy tenant identifier")
    device_type = models.CharField(max_length=50, blank=True, help_text="Type of device")
    
    is_active = models.BooleanField(default=True, help_text="Whether device is active")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'devices'
        # Ensure unique device names per organization
        unique_together = [('organization', 'name')]
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['creator', '-created_at']),
            models.Index(fields=['uuid']),
            models.Index(fields=['token']),
            models.Index(fields=['status', 'is_active']),
            # Legacy indexes
            models.Index(fields=['user', 'tenant_id']),
            models.Index(fields=['device_id']),
        ]
    
    def save(self, *args, **kwargs):
        # Generate token if not set
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        
        # Set legacy user field to creator for backward compatibility
        if not self.user_id:
            self.user = self.creator
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} ({self.organization.name})"
    
    def get_project_count(self):
        """Get number of projects this device is assigned to"""
        return self.projects.count()
    
    def assign_to_project(self, project):
        """Assign device to a project"""
        if project.organization != self.organization:
            raise ValueError("Device and project must belong to the same organization")
        self.projects.add(project)
    
    def unassign_from_project(self, project):
        """Remove device from a project"""
        self.projects.remove(project)


class MqttCluster(models.Model):
    """Model to store MQTT cluster/broker configurations"""
    
    CLUSTER_TYPES = [
        ('hosted', 'Hosted by EdgeSync'),
        ('external', 'External/Third-party'),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=200, help_text="Display name for the cluster")
    cluster_type = models.CharField(max_length=20, choices=CLUSTER_TYPES, default='external')
    user = models.ForeignKey(User, on_delete=models.CASCADE, help_text="Cluster owner")
    organization = models.ForeignKey(
        'user.Organization', 
        on_delete=models.CASCADE, 
        help_text="Organization this cluster belongs to",
        null=True,
        blank=True
    )
    
    # Connection Details
    host = models.CharField(max_length=255, help_text="MQTT broker hostname/IP")
    port = models.IntegerField(default=1883, help_text="MQTT broker port")
    use_ssl = models.BooleanField(default=False, help_text="Use SSL/TLS connection")
    
    # Authentication
    username = models.CharField(max_length=100, blank=True, help_text="MQTT username")
    password = models.CharField(max_length=255, blank=True, help_text="MQTT password (encrypted)")
    
    # Metadata
    description = models.TextField(blank=True, help_text="Cluster description")
    is_active = models.BooleanField(default=True, help_text="Whether cluster is active")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Stats (can be updated periodically)
    total_topics = models.IntegerField(default=0, help_text="Number of active topics")
    total_messages = models.BigIntegerField(default=0, help_text="Total messages published")
    total_subscriptions = models.IntegerField(default=0, help_text="Number of active subscriptions")
    
    class Meta:
        db_table = 'mqtt_clusters'
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['cluster_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.cluster_type})"
    
    @property
    def connection_url(self):
        """Generate MQTT connection URL"""
        protocol = 'mqtts' if self.use_ssl else 'mqtt'
        if self.username:
            return f"{protocol}://{self.username}:***@{self.host}:{self.port}"
        return f"{protocol}://{self.host}:{self.port}"


class MqttTopic(models.Model):
    """Model to track MQTT topics and their activity"""
    
    cluster = models.ForeignKey(MqttCluster, on_delete=models.CASCADE, related_name='topics')
    topic_name = models.CharField(max_length=255, help_text="MQTT topic name")
    
    # Activity tracking
    message_count = models.BigIntegerField(default=0, help_text="Total messages on this topic")
    last_message_at = models.DateTimeField(null=True, blank=True, help_text="When last message was received")
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'mqtt_topics'
        unique_together = ['cluster', 'topic_name']
        indexes = [
            models.Index(fields=['cluster', '-last_message_at']),
            models.Index(fields=['cluster', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.cluster.name}: {self.topic_name}"


class MqttActivity(models.Model):
    """Model to log MQTT activity for monitoring"""
    
    ACTIVITY_TYPES = [
        ('publish', 'Message Published'),
        ('subscribe', 'Topic Subscribed'),
        ('unsubscribe', 'Topic Unsubscribed'),
        ('connect', 'Client Connected'),
        ('disconnect', 'Client Disconnected'),
    ]
    
    cluster = models.ForeignKey(MqttCluster, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    topic_name = models.CharField(max_length=255, blank=True, help_text="Associated topic")
    client_id = models.CharField(max_length=255, blank=True, help_text="MQTT client ID")
    message_size = models.IntegerField(null=True, blank=True, help_text="Message size in bytes")
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'mqtt_activities'
        indexes = [
            models.Index(fields=['cluster', '-timestamp']),
            models.Index(fields=['activity_type', '-timestamp']),
            models.Index(fields=['cluster', 'topic_name', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.cluster.name}: {self.activity_type} at {self.timestamp}"


# ---------------------------------------------------------------------------
# Dashboard-widget tracking models (short-term buffer for live sensor widgets)
# ---------------------------------------------------------------------------

class TrackedVariable(models.Model):
    """Identifies which device/sensor values should be persisted for a widget."""

    device_id = models.CharField(max_length=100)
    sensor_type = models.CharField(max_length=50)

    # Widget + dashboard this variable feeds
    widget_id = models.CharField(max_length=100)
    dashboard_uuid = models.CharField(max_length=36)

    max_samples = models.IntegerField(default=50, help_text="How many samples to retain")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tracked_variables'
        unique_together = [('device_id', 'sensor_type', 'widget_id')]
        indexes = [
            models.Index(fields=['device_id', 'sensor_type']),
            models.Index(fields=['widget_id']),
        ]

    def __str__(self):
        return f"{self.device_id}:{self.sensor_type} → widget {self.widget_id}"


class WidgetSample(models.Model):
    """Circular-buffer sample for a widget (max 50 rows per tracked variable)."""

    widget = models.ForeignKey(
        TrackedVariable,
        on_delete=models.CASCADE,
        related_name='samples'
    )
    timestamp = models.DateTimeField()
    value = models.FloatField()
    unit = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['-timestamp']
        db_table = 'widget_samples'
        indexes = [
            models.Index(fields=['widget', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.widget.widget_id} @ {self.timestamp}: {self.value}{self.unit}"


