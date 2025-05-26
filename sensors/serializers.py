from rest_framework import serializers
from .models import SensorData

class SensorDataSerializer(serializers.ModelSerializer):
    """Serializer for SensorData model"""
    
    class Meta:
        model = SensorData
        fields = ['id', 'device_id', 'sensor_type', 'value', 'unit', 'timestamp', 'raw_data']
        read_only_fields = ['id', 'timestamp'] 