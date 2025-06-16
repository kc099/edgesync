from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json
import uuid

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
    """Model to store IoT device information"""
    
    device_id = models.CharField(max_length=100, unique=True, help_text="Unique device identifier")
    device_name = models.CharField(max_length=200, help_text="Human readable device name")
    user = models.ForeignKey(User, on_delete=models.CASCADE, help_text="Device owner")
    organization = models.ForeignKey(
        'user.Organization', 
        on_delete=models.CASCADE, 
        help_text="Organization this device belongs to",
        null=True,
        blank=True
    )
    tenant_id = models.CharField(max_length=100, help_text="Tenant identifier")
    device_type = models.CharField(max_length=50, help_text="Type of device")
    is_active = models.BooleanField(default=True, help_text="Whether device is active")
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'devices'
        indexes = [
            models.Index(fields=['user', 'tenant_id']),
            models.Index(fields=['device_id']),
            models.Index(fields=['organization', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.device_name} ({self.device_id})"


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


