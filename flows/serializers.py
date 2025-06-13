from rest_framework import serializers
from .models import FlowDiagram, FlowExecution, NodeExecution

class FlowDiagramSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowDiagram
        fields = ['id', 'name', 'description', 'nodes', 'edges', 'metadata', 
                 'is_active', 'created_at', 'updated_at', 'version', 'tags']
        read_only_fields = ['created_at', 'updated_at']

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