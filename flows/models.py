from django.db import models
from django.contrib.auth.models import User
import json
import uuid

class FlowDiagram(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    project = models.ForeignKey('user.Project', on_delete=models.CASCADE, related_name='flows', null=True, blank=True)
    nodes = models.JSONField(default=list)  # Store React Flow nodes
    edges = models.JSONField(default=list)  # Store React Flow edges
    metadata = models.JSONField(default=dict)  # Additional flow metadata
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.CharField(max_length=20, default='1.0.0')
    tags = models.JSONField(default=list)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

class FlowExecution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('stopped', 'Stopped')
    ]
    
    flow = models.ForeignKey(FlowDiagram, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"Execution {self.id} - {self.flow.name} ({self.status})"

class NodeExecution(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]
    
    flow_execution = models.ForeignKey(FlowExecution, on_delete=models.CASCADE)
    node_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(default=dict)
    executed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(default=0)

    def __str__(self):
        return f"Node {self.node_id} - Execution {self.flow_execution.id} ({self.status})"

class FlowNodeOutput(models.Model):
    """
    Store flow node outputs for dashboard visualization.
    """
    flow_execution = models.ForeignKey(FlowExecution, on_delete=models.CASCADE, related_name='node_outputs')
    node_id = models.CharField(max_length=100)
    output_data = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'flow_node_outputs'
        indexes = [
            models.Index(fields=['flow_execution', 'node_id', '-timestamp']),
            models.Index(fields=['node_id', '-timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Output from {self.node_id} at {self.timestamp}"

class DashboardWidget(models.Model):
    """
    Link dashboard widgets to flow node outputs with data source configuration.
    """
    DATA_SOURCE_CHOICES = [
        ('flow_node', 'Flow Node Output'),
        ('device_sensor', 'Device Sensor'),
        ('static', 'Static Data'),
    ]
    
    AGGREGATION_CHOICES = [
        ('last', 'Latest Value'),
        ('avg', 'Average'),
        ('sum', 'Sum'),
        ('count', 'Count'),
        ('min', 'Minimum'),
        ('max', 'Maximum'),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    
    # Dashboard relationship
    dashboard_template_uuid = models.CharField(max_length=36)  # Store UUID as string for flexibility
    widget_id = models.CharField(max_length=100)  # Widget ID in dashboard template
    
    # Data source configuration
    data_source_type = models.CharField(
        max_length=20,
        choices=DATA_SOURCE_CHOICES,
        default='flow_node'
    )
    
    # Flow node data source
    flow = models.ForeignKey(FlowDiagram, on_delete=models.CASCADE, null=True, blank=True)
    node_id = models.CharField(max_length=100, blank=True)
    output_field = models.CharField(max_length=100, default='output')  # Field from node output
    
    # Real-time configuration
    auto_refresh = models.BooleanField(default=True)
    refresh_interval = models.IntegerField(default=30000)  # milliseconds
    
    # Data transformation
    data_transform = models.TextField(blank=True)  # JavaScript function string
    aggregation_type = models.CharField(
        max_length=20,
        choices=AGGREGATION_CHOICES,
        default='last'
    )
    
    # Widget metadata
    widget_title = models.CharField(max_length=200)
    widget_type = models.CharField(max_length=50)
    widget_config = models.JSONField(default=dict)
    
    # Grid layout information
    grid_position = models.JSONField(default=dict)  # Store x, y, w, h, minW, minH
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dashboard_widgets'
        unique_together = [('dashboard_template_uuid', 'widget_id')]
        indexes = [
            models.Index(fields=['dashboard_template_uuid']),
            models.Index(fields=['flow', 'node_id']),
            models.Index(fields=['data_source_type']),
        ]
    
    def __str__(self):
        return f"Widget {self.widget_title} ({self.widget_type})"
    
    def get_latest_output(self):
        """Get the latest output for this widget's flow node."""
        if self.data_source_type == 'flow_node' and self.flow and self.node_id:
            return FlowNodeOutput.objects.filter(
                flow_execution__flow=self.flow,
                node_id=self.node_id
            ).first()
        return None
    
    def get_output_history(self, hours=24, limit=1000):
        """Get historical outputs for this widget's flow node."""
        if self.data_source_type == 'flow_node' and self.flow and self.node_id:
            from django.utils import timezone
            from datetime import timedelta
            
            since_time = timezone.now() - timedelta(hours=hours)
            return FlowNodeOutput.objects.filter(
                flow_execution__flow=self.flow,
                node_id=self.node_id,
                timestamp__gte=since_time
            ).order_by('timestamp')[:limit]
        return FlowNodeOutput.objects.none()
