from django.db import models
from django.utils import timezone
import json

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
