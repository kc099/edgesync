from django.db import models
from django.contrib.auth.models import User
import json

class FlowDiagram(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
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
