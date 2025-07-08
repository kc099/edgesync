from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import FlowDiagram, FlowExecution
from .serializers import FlowDiagramSerializer, FlowExecutionSerializer

# Create your views here.

@extend_schema_view(
    list=extend_schema(
        operation_id='list_flows',
        tags=['Flows'],
        summary='List Flow Diagrams',
        description='Retrieve all flow diagrams for the current user. Optionally filter by project.',
        parameters=[
            {
                'name': 'project_uuid',
                'description': 'Filter flows by project UUID',
                'required': False,
                'type': 'string',
                'in': 'query'
            }
        ]
    ),
    create=extend_schema(
        operation_id='create_flow',
        tags=['Flows'],
        summary='Create Flow Diagram',
        description='Create a new flow diagram'
    ),
    retrieve=extend_schema(
        operation_id='get_flow',
        tags=['Flows'],
        summary='Get Flow Diagram',
        description='Retrieve a specific flow diagram by UUID'
    ),
    update=extend_schema(
        operation_id='update_flow',
        tags=['Flows'],
        summary='Update Flow Diagram',
        description='Update a flow diagram'
    ),
    partial_update=extend_schema(
        operation_id='partial_update_flow',
        tags=['Flows'],
        summary='Partially Update Flow Diagram',
        description='Partially update a flow diagram'
    ),
    destroy=extend_schema(
        operation_id='delete_flow',
        tags=['Flows'],
        summary='Delete Flow Diagram',
        description='Delete a flow diagram'
    ),
)
class FlowDiagramViewSet(viewsets.ModelViewSet):
    serializer_class = FlowDiagramSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'uuid'

    def get_queryset(self):
        queryset = FlowDiagram.objects.filter(owner=self.request.user)
        
        # Filter by project if project_uuid is provided
        project_uuid = self.request.query_params.get('project_uuid', None)
        if project_uuid is not None:
            queryset = queryset.filter(project__uuid=project_uuid)
        
        return queryset

    def perform_create(self, serializer):
        # Get project from request data if provided
        project_uuid = self.request.data.get('project_uuid', None)
        if project_uuid:
            from user.models import Project
            try:
                project = Project.objects.get(
                    uuid=project_uuid,
                    organization__members__user=self.request.user
                )
                serializer.save(owner=self.request.user, project=project)
            except Project.DoesNotExist:
                serializer.save(owner=self.request.user)
        else:
            serializer.save(owner=self.request.user)

    @extend_schema(
        operation_id='execute_flow',
        tags=['Flows'],
        summary='Execute Flow Diagram',
        description='Execute a flow diagram and start processing',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'execution_id': {'type': 'integer'},
                    'status': {'type': 'string'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute a flow diagram"""
        flow = self.get_object()
        
        try:
            # Import the flow executor
            from .engine.flow_executor import FlowExecutor, ExecutionStrategy
            
            # Get execution parameters from request
            execution_strategy = request.data.get('strategy', 'hybrid')
            max_workers = request.data.get('max_workers', 4)
            trigger_data = request.data.get('trigger_data', {})
            
            # Map string strategy to enum
            strategy_map = {
                'sequential': ExecutionStrategy.SEQUENTIAL,
                'parallel': ExecutionStrategy.PARALLEL,
                'hybrid': ExecutionStrategy.HYBRID
            }
            strategy = strategy_map.get(execution_strategy, ExecutionStrategy.HYBRID)
            
            # Execute the flow
            result = FlowExecutor.create_and_execute(
                flow_diagram=flow,
                trigger_data=trigger_data,
                execution_strategy=strategy,
                max_workers=max_workers
            )
            
            return Response({
                'success': True,
                'execution_id': result['execution_id'],
                'flow_id': result['flow_id'],
                'status': 'completed',
                'message': 'Flow execution completed successfully',
                'results': result['execution_results']['execution_summary'],
                'dependency_info': result['dependency_info']
            })
            
        except Exception as e:
            # Create failed execution record
            execution = FlowExecution.objects.create(
                flow=flow,
                status='failed',
                error_message=str(e)
            )
            
            return Response({
                'success': False,
                'execution_id': execution.id,
                'status': 'failed',
                'message': f'Flow execution failed: {str(e)}',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        operation_id='duplicate_flow',
        tags=['Flows'],
        summary='Duplicate Flow Diagram',
        description='Create a copy of an existing flow diagram',
        responses={
            201: {
                'type': 'object',
                'description': 'Duplicated flow diagram data'
            }
        }
    )
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a flow diagram"""
        original_flow = self.get_object()
        new_flow = FlowDiagram.objects.create(
            name=f"{original_flow.name} (Copy)",
            description=original_flow.description,
            owner=request.user,
            project=original_flow.project,  # Keep the same project
            nodes=original_flow.nodes,
            edges=original_flow.edges,
            metadata=original_flow.metadata,
            tags=original_flow.tags
        )
        serializer = self.get_serializer(new_flow)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id='get_flow_templates',
        tags=['Flows'],
        summary='Get Flow Templates',
        description='Retrieve predefined flow diagram templates',
        responses={
            200: {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'description': {'type': 'string'},
                        'nodes': {'type': 'array'},
                        'edges': {'type': 'array'},
                        'tags': {'type': 'array'}
                    }
                }
            }
        }
    )
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
