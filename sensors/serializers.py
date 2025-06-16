from rest_framework import serializers
from .models import SensorData, MqttCluster, MqttTopic, MqttActivity

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


class MqttClusterSerializer(serializers.ModelSerializer):
    """Serializer for MQTT Cluster model"""
    
    # Nested relations
    topics = MqttTopicSerializer(many=True, read_only=True)
    recent_activities = serializers.SerializerMethodField()
    connection_url = serializers.ReadOnlyField()
    
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
    
    def get_recent_activities(self, obj):
        """Get recent activities for this cluster"""
        recent = obj.activities.order_by('-timestamp')[:10]
        return MqttActivitySerializer(recent, many=True).data
    
    def create(self, validated_data):
        # Set user from request context
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class MqttClusterListSerializer(serializers.ModelSerializer):
    """Simplified serializer for cluster listing"""
    
    connection_url = serializers.ReadOnlyField()
    
    class Meta:
        model = MqttCluster
        fields = [
            'uuid', 'name', 'cluster_type', 'host', 'port', 'use_ssl',
            'description', 'is_active', 'created_at',
            'total_topics', 'total_messages', 'total_subscriptions',
            'connection_url'
        ]
        read_only_fields = ['uuid', 'created_at', 'connection_url']