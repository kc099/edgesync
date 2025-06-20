from rest_framework import serializers
from .models import SensorData, MqttCluster, MqttTopic, MqttActivity
from typing import List, Dict, Any

class SensorDataSerializer(serializers.ModelSerializer):
    """Serializer for SensorData model"""
    
    class Meta:
        model = SensorData
        fields = ['id', 'device_id', 'sensor_type', 'value', 'unit', 'timestamp', 'raw_data']
        read_only_fields = ['id', 'timestamp']


class MqttTopicSerializer(serializers.ModelSerializer):
    """Serializer for MQTT Topic model"""
    
    class Meta:
        model = MqttTopic
        fields = ['id', 'topic_name', 'message_count', 'last_message_at', 'created_at', 'is_active']
        read_only_fields = ['id', 'created_at']


class MqttActivitySerializer(serializers.ModelSerializer):
    """Serializer for MQTT Activity model"""
    
    class Meta:
        model = MqttActivity
        fields = ['id', 'activity_type', 'topic_name', 'client_id', 'message_size', 'timestamp']
        read_only_fields = ['id', 'timestamp']


# New serializers for ACL and Device operations
class ACLSerializer(serializers.Serializer):
    """Serializer for MQTT ACL operations"""
    id = serializers.CharField(read_only=True)
    topicPattern = serializers.CharField(max_length=255)
    accessType = serializers.IntegerField(min_value=1, max_value=4)
    
    def validate_accessType(self, value):
        """Validate access type values"""
        if value not in [1, 2, 3, 4]:  # 1=read, 2=write, 3=read/write, 4=subscribe
            raise serializers.ValidationError("Access type must be 1(read), 2(write), 3(read/write), or 4(subscribe)")
        return value


class DeviceSerializer(serializers.Serializer):
    """Serializer for Device operations"""
    deviceId = serializers.CharField(max_length=100)
    deviceName = serializers.CharField(max_length=255)
    deviceType = serializers.CharField(max_length=100)
    tenantId = serializers.CharField(max_length=100)
    isActive = serializers.BooleanField(default=True)
    createdAt = serializers.DateTimeField(read_only=True)
    permissions = serializers.ListField(
        child=serializers.CharField(max_length=20),
        read_only=True
    )


class DeviceCreateSerializer(serializers.Serializer):
    """Serializer for creating devices"""
    deviceId = serializers.CharField(max_length=100)
    deviceName = serializers.CharField(max_length=255)
    deviceType = serializers.CharField(max_length=100)
    tenantId = serializers.CharField(max_length=100)
    permissions = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False
    )


class DeviceUpdateSerializer(serializers.Serializer):
    """Serializer for updating devices"""
    deviceName = serializers.CharField(max_length=255, required=False)
    isActive = serializers.BooleanField(required=False)


class MqttPasswordSerializer(serializers.Serializer):
    """Serializer for setting MQTT password"""
    username = serializers.CharField(max_length=100, min_length=3)
    password = serializers.CharField(max_length=255, min_length=8, write_only=True)
    
    def validate_username(self, value):
        """Validate username format"""
        if not value.replace('_', '').isalnum():
            raise serializers.ValidationError("Username can only contain letters, numbers, and underscores")
        return value


class MqttClusterSerializer(serializers.ModelSerializer):
    """Serializer for MQTT Cluster model"""
    
    # Nested relations
    topics = MqttTopicSerializer(many=True, read_only=True)
    recent_activities = serializers.SerializerMethodField()
    connection_url = serializers.SerializerMethodField()
    
    class Meta:
        model = MqttCluster
        fields = [
            'uuid', 'name', 'cluster_type', 'host', 'port', 'use_ssl',
            'username', 'description', 'is_active', 'created_at', 'updated_at',
            'total_topics', 'total_messages', 'total_subscriptions',
            'connection_url', 'topics', 'recent_activities'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at', 'connection_url']
        extra_kwargs = {
            'password': {'write_only': True}  # Never return password in API
        }
    
    def get_recent_activities(self, obj) -> List[Dict[str, Any]]:
        """Get recent activities for this cluster"""
        recent = obj.activities.order_by('-timestamp')[:10]
        return MqttActivitySerializer(recent, many=True).data
    
    def get_connection_url(self, obj) -> str:
        """Get the connection URL for this cluster"""
        protocol = "mqtts" if obj.use_ssl else "mqtt"
        return f"{protocol}://{obj.host}:{obj.port}"
    
    def create(self, validated_data):
        # Set user from request context
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class MqttClusterListSerializer(serializers.ModelSerializer):
    """Simplified serializer for cluster listing"""
    
    connection_url = serializers.SerializerMethodField()
    
    class Meta:
        model = MqttCluster
        fields = [
            'uuid', 'name', 'cluster_type', 'host', 'port', 'use_ssl',
            'description', 'is_active', 'created_at',
            'total_topics', 'total_messages', 'total_subscriptions',
            'connection_url'
        ]
        read_only_fields = ['uuid', 'created_at', 'connection_url']
    
    def get_connection_url(self, obj) -> str:
        """Get the connection URL for this cluster"""
        protocol = "mqtts" if obj.use_ssl else "mqtt"
        return f"{protocol}://{obj.host}:{obj.port}"