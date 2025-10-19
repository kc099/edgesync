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
    def execute(self, request, uuid=None):
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
    def duplicate(self, request, uuid=None):
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

    @extend_schema(
        operation_id='get_node_output',
        tags=['Flows'],
        summary='Get Flow Node Output',
        description='Get current output data from a specific flow node',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'node_id': {'type': 'string'},
                    'output_data': {'type': 'object'},
                    'timestamp': {'type': 'string'},
                    'execution_id': {'type': 'integer'}
                }
            }
        }
    )
    @action(detail=True, methods=['get'], url_path='nodes/(?P<node_id>[^/.]+)/output')
    def get_node_output(self, request, uuid=None, node_id=None):
        """Get current output from a flow node or device node"""
        flow = self.get_object()
        
        try:
            # Get latest output for this node from FlowNodeOutput table
            from .models import FlowNodeOutput
            latest_output = FlowNodeOutput.objects.filter(
                flow_execution__flow=flow,
                node_id=node_id
            ).first()
            if latest_output:
                return Response({
                    'node_id': node_id,
                    'output': latest_output.output_data,
                    'timestamp': latest_output.timestamp.isoformat(),
                    'execution_id': latest_output.flow_execution.id,
                    'message': 'Flow node output data retrieved'
                })
            
            # If no flow node output, check if this is a device node
            # Device nodes have UUIDs as node_id, try to get latest sensor data
            try:
                from sensors.models import SensorData
                from django.utils import timezone
                from datetime import timedelta
                
                # Get recent sensor data for this device (last 5 minutes)
                recent_time = timezone.now() - timedelta(minutes=5)
                
                # Check if a specific sensor type is requested
                sensor_type = request.GET.get('sensor_type')
                if sensor_type:
                    recent_data = SensorData.objects.filter(
                        device_id=node_id,
                        sensor_type=sensor_type,
                        timestamp__gte=recent_time
                    ).order_by('-timestamp').first()
                else:
                    recent_data = SensorData.objects.filter(
                        device_id=node_id,
                        timestamp__gte=recent_time
                    ).order_by('-timestamp').first()
                
                if recent_data:
                    return Response({
                        'node_id': node_id,
                        'output': {
                            'device_id': recent_data.device_id,
                            'sensor_type': recent_data.sensor_type,
                            'value': recent_data.value,
                            'unit': recent_data.unit,
                            'timestamp': recent_data.timestamp.isoformat()
                        },
                        'timestamp': recent_data.timestamp.isoformat(),
                        'message': 'Device sensor data retrieved'
                    })
                else:
                    return Response({
                        'node_id': node_id,
                        'output': None,
                        'timestamp': None,
                        'message': 'No recent device data available (last 5 minutes)'
                    })
            except Exception as device_error:
                return Response({
                    'node_id': node_id,
                    'output': None,
                    'timestamp': None,
                    'message': 'No output data available'
                })
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        operation_id='get_node_output_history',
        tags=['Flows'],
        summary='Get Flow Node Output History',
        description='Get historical output data from a specific flow node',
        parameters=[
            {
                'name': 'limit',
                'description': 'Maximum number of records to return',
                'required': False,
                'type': 'integer',
                'in': 'query'
            },
            {
                'name': 'hours',
                'description': 'Number of hours to look back',
                'required': False,
                'type': 'integer',
                'in': 'query'
            }
        ]
    )
    @action(detail=True, methods=['get'], url_path='nodes/(?P<node_id>[^/.]+)/output/history')
    def get_node_output_history(self, request, uuid=None, node_id=None):
        """Get historical output from a flow node"""
        flow = self.get_object()
        
        # Query parameters
        limit = int(request.query_params.get('limit', 100))
        hours = int(request.query_params.get('hours', 24))
        
        try:
            # Use FlowNodeOutput records for historical data
            from .models import FlowNodeOutput
            from django.utils import timezone
            from datetime import timedelta

            since_time = timezone.now() - timedelta(hours=hours)
            outputs = FlowNodeOutput.objects.filter(
                flow_execution__flow=flow,
                node_id=node_id,
                timestamp__gte=since_time
            ).order_by('-timestamp')[:limit]
            return Response({
                'node_id': node_id,
                'data': [
                    {
                        'output_data': output.output_data,
                        'timestamp': output.timestamp.isoformat(),
                        'execution_id': output.flow_execution.id,
                    }
                    for output in outputs
                ],
                'count': len(outputs),
                'time_range': {
                    'since': since_time.isoformat(),
                    'until': timezone.now().isoformat(),
                },
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        operation_id='create_widget_from_node',
        tags=['Flows'],
        summary='Create Dashboard Widget from Flow Node',
        description='Create a dashboard widget linked to flow node output',
        request={
            'type': 'object',
            'properties': {
                'dashboard_uuid': {'type': 'string'},
                'widget_type': {'type': 'string'},
                'widget_title': {'type': 'string'},
                'output_field': {'type': 'string'},
                'auto_refresh': {'type': 'boolean'},
                'refresh_interval': {'type': 'integer'},
                'widget_config': {'type': 'object'}
            },
            'required': ['dashboard_uuid', 'widget_type', 'widget_title']
        }
    )
    @action(detail=True, methods=['post'], url_path='nodes/(?P<node_id>.*)/create-widget')
    def create_widget_from_node(self, request, uuid=None, node_id=None):
        """Create a dashboard widget from flow node output - simplified approach"""
        flow = self.get_object()

        try:
            from user.models import DashboardTemplate
            from datetime import datetime
            import uuid as uuid_lib

            # Extract widget configuration from request
            widget_config = request.data

            # Validate required fields
            required_fields = ['dashboard_uuid', 'widget_type', 'widget_title']
            for field in required_fields:
                if field not in widget_config:
                    return Response({
                        'error': f'Missing required field: {field}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get dashboard template
            try:
                dashboard = DashboardTemplate.objects.get(
                    uuid=widget_config['dashboard_uuid']
                )
            except DashboardTemplate.DoesNotExist:
                return Response({
                    'error': 'Dashboard template not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Generate unique widget ID
            widget_id = f"flow-widget-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid_lib.uuid4().hex[:8]}"
            
            # Get widget dimensions based on type (same logic as frontend)
            def get_widget_dimensions(widget_type):
                dimension_map = {
                    'time_series': {'w': 6, 'h': 8, 'minW': 4, 'minH': 6},
                    'bar_chart': {'w': 6, 'h': 8, 'minW': 4, 'minH': 6},
                    'pie_chart': {'w': 6, 'h': 6, 'minW': 3, 'minH': 4},
                    'gauge': {'w': 4, 'h': 4, 'minW': 3, 'minH': 3},
                    'stat_panel': {'w': 3, 'h': 3, 'minW': 2, 'minH': 2},
                    'table': {'w': 8, 'h': 6, 'minW': 4, 'minH': 4}
                }
                return dimension_map.get(widget_type, {'w': 6, 'h': 6, 'minW': 3, 'minH': 4})
            
            # Create simple widget configuration - no grid layout complexity
            widget_data = {
                'id': widget_id,
                'type': widget_config['widget_type'],
                'title': widget_config['widget_title'],
                'config': widget_config.get('widget_config', {}),
                'dataSource': {
                    'type': 'flow_node',
                    'flowUuid': str(flow.uuid),
                    'nodeId': node_id,
                    'nodeName': widget_config.get('node_name', 'Flow Node'),
                    'autoRefresh': True,
                    'refreshInterval': 30000  # 30 seconds
                }
            }

            # Create layout entry for the widget
            dimensions = get_widget_dimensions(widget_config['widget_type'])
            
            # Use the same positioning logic as frontend - let react-grid-layout auto-place
            layout_entry = {
                'i': widget_id,
                'x': 0,
                'y': 9999,  # Large number to place at bottom (react-grid-layout will compact)
                **dimensions
            }

            # If this is a device node with a variable, register TrackedVariable
            try:
                parts = node_id.split('-')
                if len(parts) >= 5:
                    device_uuid = '-'.join(parts[:5])

                    from sensors.models import Device
                    try:
                        device = Device.objects.get(uuid=device_uuid)

                        node_map = {n['id']: n for n in flow.nodes}
                        node_cfg = node_map.get(node_id, {})
                        node_data = node_cfg.get('data', {})

                        sensor_var = (
                            widget_config.get('sensor_variable') or
                            node_data.get('config', {}).get('variable') or
                            node_data.get('variable') or
                            None
                        )

                        if sensor_var and sensor_var.strip():
                            from sensors.models import TrackedVariable
                            tracked_var, created = TrackedVariable.objects.update_or_create(
                                device_id=device_uuid,
                                sensor_type=sensor_var,
                                widget_id=widget_id,
                                defaults={
                                    'dashboard_uuid': widget_config['dashboard_uuid'],
                                    'max_samples': 50,
                                }
                            )

                    except Device.DoesNotExist:
                        pass

            except Exception as tv_err:
                pass
            
            # Add widget to dashboard widgets list
            if not dashboard.widgets:
                dashboard.widgets = []
            dashboard.widgets.append(widget_data)
            
            # Add layout entry to dashboard layout
            if not dashboard.layout:
                dashboard.layout = []
            dashboard.layout.append(layout_entry)
            
            # Save dashboard with new widget and layout
            dashboard.save()
            
            return Response({
                'success': True,
                'widget_id': widget_id,
                'dashboard_uuid': str(dashboard.uuid),
                'message': 'Widget created successfully',
                'widget_config': widget_data,
                'layout_entry': layout_entry
            })
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
