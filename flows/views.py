from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import FlowDiagram, FlowExecution
from .serializers import FlowDiagramSerializer, FlowExecutionSerializer

# Create your views here.

class FlowDiagramViewSet(viewsets.ModelViewSet):
    serializer_class = FlowDiagramSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uuid'

    def get_queryset(self):
        return FlowDiagram.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute a flow diagram"""
        flow = self.get_object()
        execution = FlowExecution.objects.create(
            flow=flow,
            status='pending'
        )
        
        # TODO: Implement flow execution logic
        # This would involve processing nodes based on their connections
        # and executing the appropriate logic for each node type
        
        return Response({
            'execution_id': execution.id,
            'status': 'started',
            'message': 'Flow execution started'
        })

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a flow diagram"""
        original_flow = self.get_object()
        new_flow = FlowDiagram.objects.create(
            name=f"{original_flow.name} (Copy)",
            description=original_flow.description,
            owner=request.user,
            nodes=original_flow.nodes,
            edges=original_flow.edges,
            metadata=original_flow.metadata,
            tags=original_flow.tags
        )
        serializer = self.get_serializer(new_flow)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def templates(self, request):
        """Get predefined flow templates"""
        templates = [
            {
                'name': 'IoT Data Pipeline',
                'description': 'Basic IoT sensor data processing pipeline',
                'nodes': [
                    {
                        'id': 'input-1',
                        'type': 'input',
                        'position': {'x': 100, 'y': 100},
                        'data': {'label': 'MQTT Input', 'nodeType': 'mqtt'}
                    },
                    {
                        'id': 'function-1',
                        'type': 'function',
                        'position': {'x': 300, 'y': 100},
                        'data': {'label': 'Process Data', 'nodeType': 'transform'}
                    },
                    {
                        'id': 'output-1',
                        'type': 'output',
                        'position': {'x': 500, 'y': 100},
                        'data': {'label': 'Database Store', 'nodeType': 'database'}
                    }
                ],
                'edges': [
                    {
                        'id': 'e1-2',
                        'source': 'input-1',
                        'target': 'function-1'
                    },
                    {
                        'id': 'e2-3',
                        'source': 'function-1',
                        'target': 'output-1'
                    }
                ],
                'tags': ['iot', 'template']
            },
            {
                'name': 'Data Analytics Flow',
                'description': 'Process and analyze sensor data',
                'nodes': [
                    {
                        'id': 'input-1',
                        'type': 'input',
                        'position': {'x': 100, 'y': 100},
                        'data': {'label': 'Sensor Input', 'nodeType': 'sensor'}
                    },
                    {
                        'id': 'function-1',
                        'type': 'function',
                        'position': {'x': 300, 'y': 100},
                        'data': {'label': 'Moving Average', 'nodeType': 'moving-average'}
                    },
                    {
                        'id': 'debug-1',
                        'type': 'debug',
                        'position': {'x': 500, 'y': 100},
                        'data': {'label': 'Debug Output', 'nodeType': 'debug'}
                    }
                ],
                'edges': [
                    {
                        'id': 'e1-2',
                        'source': 'input-1',
                        'target': 'function-1'
                    },
                    {
                        'id': 'e2-3',
                        'source': 'function-1',
                        'target': 'debug-1'
                    }
                ],
                'tags': ['analytics', 'template']
            }
        ]
        return Response(templates)
