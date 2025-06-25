from rest_framework import serializers
from .models import SensorData, Device, MqttCluster, MqttTopic, MqttActivity
from typing import List, Dict, Any

class SensorDataSerializer(serializers.ModelSerializer):
    """Serializer for SensorData model"""
    
    class Meta:
        model = SensorData
        fields = ['id', 'device_id', 'sensor_type', 'value', 'unit', 'timestamp', 'raw_data']
        read_only_fields = ['id', 'timestamp']


class DeviceListSerializer(serializers.ModelSerializer):
    """Simplified serializer for device listing"""
    
    project_count = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    
    class Meta:
        model = Device
        fields = [
            'uuid', 'name', 'description', 'status', 'last_seen',
            'organization_name', 'creator_name', 'project_count',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']
    
    def get_project_count(self, obj):
        return obj.get_project_count()


class DeviceSerializer(serializers.ModelSerializer):
    """Full serializer for Device model with project relations"""
    
    project_count = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    assigned_projects = serializers.SerializerMethodField()
    token = serializers.CharField(read_only=True)  # Token is read-only for security
    
    class Meta:
        model = Device
        fields = [
            'uuid', 'name', 'description', 'token', 'status', 'last_seen',
            'organization', 'organization_name', 'creator', 'creator_name',
            'assigned_projects', 'project_count', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'token', 'creator', 'created_at', 'updated_at']
    
    def get_project_count(self, obj):
        return obj.get_project_count()
    
    def get_assigned_projects(self, obj):
        from user.serializers import ProjectListSerializer
        return ProjectListSerializer(obj.projects.all(), many=True).data
    
    def create(self, validated_data):
        # Set creator from request context
        validated_data['creator'] = self.context['request'].user
        return super().create(validated_data)


class DeviceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating devices with project assignment"""
    
    project_uuids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True,
        help_text="List of project UUIDs to assign the device to"
    )
    token = serializers.CharField(read_only=True)  # Return token only on creation
    
    class Meta:
        model = Device
        fields = [
            'uuid', 'name', 'description', 'organization', 'status',
            'project_uuids', 'token', 'is_active'
        ]
        read_only_fields = ['uuid', 'token']
    
    def create(self, validated_data):
        project_uuids = validated_data.pop('project_uuids', [])
        
        # Set creator from request context
        validated_data['creator'] = self.context['request'].user
        
        # Create device
        device = super().create(validated_data)
        
        # Assign to projects if specified
        if project_uuids:
            from user.models import Project
            projects = Project.objects.filter(
                uuid__in=project_uuids,
                organization=device.organization
            )
            device.projects.set(projects)
        
        return device


class DeviceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating devices"""
    
    class Meta:
        model = Device
        fields = ['name', 'description', 'status', 'is_active']


class DeviceProjectAssignmentSerializer(serializers.Serializer):
    """Serializer for assigning/unassigning devices to projects"""
    
    project_uuid = serializers.UUIDField()
    
    def validate_project_uuid(self, value):
        from user.models import Project
        
        device = self.context.get('device')
        if not device:
            raise serializers.ValidationError("Device context not provided")
        
        try:
            project = Project.objects.get(uuid=value, organization=device.organization)
            return value
        except Project.DoesNotExist:
            raise serializers.ValidationError("Project not found in the same organization")


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