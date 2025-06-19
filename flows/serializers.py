from rest_framework import serializers
from .models import FlowDiagram, FlowExecution, NodeExecution

class FlowDiagramSerializer(serializers.ModelSerializer):
    project_uuid = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    
    class Meta:
        model = FlowDiagram
        fields = ['uuid', 'id', 'name', 'description', 'project_uuid', 'project_name', 
                 'nodes', 'edges', 'metadata', 'is_active', 'created_at', 'updated_at', 
                 'version', 'tags']
        read_only_fields = ['created_at', 'updated_at', 'project_uuid', 'project_name']
    
    def get_project_uuid(self, obj):
        return str(obj.project.uuid) if obj.project else None
    
    def get_project_name(self, obj):
        return obj.project.name if obj.project else None

class FlowExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowExecution
        fields = ['id', 'flow', 'status', 'started_at', 'completed_at', 
                 'result', 'error_message']
        read_only_fields = ['started_at', 'completed_at']

class NodeExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NodeExecution
        fields = ['id', 'flow_execution', 'node_id', 'status', 'input_data', 
                 'output_data', 'executed_at', 'duration_ms'] 