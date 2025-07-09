# Phase 3: Background Task Processing Implementation Plan

## AWS Lightsail 2GB RAM Analysis & Optimization Strategy

### **Memory Footprint Analysis**

#### **Base System Requirements (2GB RAM)**
```
├── Operating System (Ubuntu)      ~400MB
├── PostgreSQL Database           ~100-200MB  
├── Django Application            ~150-300MB
├── Redis (Message Broker)        ~50-100MB
├── Nginx/Apache                  ~50MB
├── System Overhead               ~200MB
└── Available for Celery Tasks    ~800-1200MB
```

#### **Per-Flow Memory Consumption**
```python
# Estimated memory per concurrent flow:
Base Flow Execution:          ~10-20MB
├── Flow Context             ~1-2MB
├── Node Processors          ~5-10MB (depends on node count)
├── Dependency Graph         ~1-3MB
├── Execution Results        ~2-5MB
└── Python Overhead          ~1-5MB

# Device/IoT Processing:
IoT Data Processing:          ~5-15MB additional
├── WebSocket Connections    ~2-5MB
├── Sensor Data Buffering    ~2-5MB
├── Real-time Calculations   ~1-5MB
```

#### **Concurrent Flow Capacity**
```
Optimistic Scenario:  40-60 concurrent flows (20MB each)
Realistic Scenario:   25-35 concurrent flows (30MB each) 
Conservative Scenario: 15-20 concurrent flows (50MB each)
```

### **Celery Multi-Flow Capabilities**

#### ✅ **Celery CAN Handle Multiple Flows Efficiently**

**1. Task Isolation**
- Each flow execution runs as separate Celery task
- Memory released automatically after task completion
- No cross-task contamination

**2. Concurrency Models**
```python
# Option 1: Process-based (Higher isolation, more memory)
CELERY_WORKER_CONCURRENCY = 4
CELERY_WORKER_POOL = 'prefork'
# Memory: ~4 processes × 150MB = 600MB

# Option 2: Thread-based (Lower memory, shared resources)
CELERY_WORKER_CONCURRENCY = 8 
CELERY_WORKER_POOL = 'threads'
# Memory: ~1 process + 8 threads × 50MB = 400MB

# Option 3: Gevent (Async, lowest memory - RECOMMENDED)
CELERY_WORKER_CONCURRENCY = 50
CELERY_WORKER_POOL = 'gevent'
# Memory: ~1 process + async workers × 10MB = 500MB
```

**3. Queue Management**
```python
# Separate queues for different flow types
CELERY_ROUTES = {
    'flows.tasks.execute_flow': {'queue': 'flow_execution'},
    'flows.tasks.device_trigger': {'queue': 'device_events'},
    'flows.tasks.scheduled_flow': {'queue': 'scheduled_tasks'}
}
```

### **Optimized Architecture for 2GB RAM**

#### **Strategy: Lightweight + Gevent + Smart Caching**

```python
# Recommended Celery Configuration
CELERY_WORKER_POOL = 'gevent'
CELERY_WORKER_CONCURRENCY = 30
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes
CELERY_TASK_TIME_LIMIT = 600       # 10 minutes
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100  # Prevent memory leaks
```

#### **Resource Management Components**

**1. Flow Execution Pool**
```python
class FlowExecutionPool:
    """
    Manages concurrent flow execution with resource limits.
    """
    MAX_CONCURRENT_FLOWS = 20  # Conservative limit
    MEMORY_THRESHOLD = 0.8     # Stop new flows at 80% memory
    
    def can_execute_flow(self) -> bool:
        return (
            self.active_flows < self.MAX_CONCURRENT_FLOWS and
            self.get_memory_usage() < self.MEMORY_THRESHOLD
        )
```

**2. Memory-Optimized Flow Context**
```python
class LightweightExecutionContext:
    """
    Reduced memory footprint execution context.
    """
    def __init__(self):
        self._node_results = {}  # Store only essential data
        self._variables = {}     # Limit variable storage
        self._max_log_entries = 50  # Reduced logging
```

**3. Streaming Result Processing**
```python
def process_flow_results_streaming(flow_results):
    """
    Process and store results in chunks to reduce memory usage.
    """
    for chunk in chunked_results(flow_results, chunk_size=100):
        process_chunk(chunk)
        del chunk  # Explicit cleanup
```

### **Implementation Architecture**

#### **Component Stack**
```
┌─────────────────────────────────────────┐
│             Frontend (React)             │
├─────────────────────────────────────────┤
│          Django REST API                │
├─────────────────────────────────────────┤
│         Flow Execution Engine           │ 
├─────────────────────────────────────────┤
│            Celery Tasks                 │
│  ┌─────────────┬─────────────────────┐  │
│  │ Sync Flows  │   Background Flows  │  │
│  │ (< 30 sec)  │    (> 30 sec)      │  │
│  └─────────────┴─────────────────────┘  │
├─────────────────────────────────────────┤
│         Redis Message Broker            │
├─────────────────────────────────────────┤
│       PostgreSQL Database              │
└─────────────────────────────────────────┘
```

#### **Execution Flow Decision Tree**
```python
def decide_execution_method(flow_diagram):
    """
    Decide between sync vs async execution based on flow characteristics.
    """
    estimated_time = estimate_execution_time(flow_diagram)
    node_count = len(flow_diagram.nodes)
    has_device_nodes = any(node.get('type') == 'device' for node in flow_diagram.nodes)
    
    if estimated_time < 30 and node_count < 10 and not has_device_nodes:
        return 'synchronous'  # Execute immediately
    else:
        return 'asynchronous'  # Queue for background processing
```

### **Phase 3 Implementation Steps**

#### **Step 1: Celery Integration Setup**
```python
# flows/tasks.py
from celery import shared_task
from .engine.flow_executor import FlowExecutor

@shared_task(bind=True, soft_time_limit=300, time_limit=600)
def execute_flow_async(self, flow_id, trigger_data=None, execution_config=None):
    """
    Execute flow in background with resource monitoring.
    """
    try:
        # Memory check before execution
        if not check_memory_availability():
            self.retry(countdown=30, max_retries=3)
        
        flow = FlowDiagram.objects.get(id=flow_id)
        result = FlowExecutor.create_and_execute(
            flow_diagram=flow,
            trigger_data=trigger_data,
            **execution_config
        )
        
        return result
        
    except Exception as e:
        # Log error and update flow execution status
        logger.error(f"Background flow execution failed: {e}")
        raise
```

#### **Step 2: Resource Monitoring**
```python
# flows/monitoring.py
import psutil

class ResourceMonitor:
    """
    Monitor system resources and flow capacity.
    """
    
    @staticmethod
    def get_memory_usage():
        return psutil.virtual_memory().percent / 100
    
    @staticmethod
    def get_active_flow_count():
        # Count active Celery tasks
        from celery import current_app
        active_tasks = current_app.control.inspect().active()
        return sum(len(tasks) for tasks in active_tasks.values())
    
    @staticmethod
    def can_execute_new_flow():
        return (
            ResourceMonitor.get_memory_usage() < 0.8 and
            ResourceMonitor.get_active_flow_count() < 20
        )
```

#### **Step 3: Smart Flow Scheduling**
```python
# flows/scheduler.py
class FlowScheduler:
    """
    Intelligent flow scheduling based on resources and priority.
    """
    
    def schedule_flow(self, flow_diagram, priority='normal'):
        if self.should_execute_immediately(flow_diagram):
            return self.execute_synchronous(flow_diagram)
        else:
            return self.queue_background_execution(flow_diagram, priority)
    
    def should_execute_immediately(self, flow_diagram):
        # Fast, simple flows execute immediately
        return (
            len(flow_diagram.nodes) < 5 and
            not self.has_long_running_nodes(flow_diagram) and
            ResourceMonitor.can_execute_new_flow()
        )
```

#### **Step 4: Device-Triggered Flows**
```python
# flows/triggers.py
class DeviceFlowTrigger:
    """
    Handle device-triggered flow execution.
    """
    
    @staticmethod
    def on_device_data_received(device_id, sensor_data):
        # Find flows triggered by this device
        triggered_flows = FlowDiagram.objects.filter(
            is_active=True,
            metadata__triggers__device_id=device_id
        )
        
        for flow in triggered_flows:
            if FlowScheduler.can_trigger_flow(flow, sensor_data):
                execute_flow_async.delay(
                    flow_id=flow.id,
                    trigger_data={
                        'device_id': device_id,
                        'sensor_data': sensor_data,
                        'trigger_type': 'device_data'
                    }
                )
```

### **Memory Optimization Techniques**

#### **1. Result Streaming**
```python
class StreamingResultHandler:
    """
    Stream results to database instead of keeping in memory.
    """
    
    def store_node_result(self, node_id, result):
        # Store immediately, don't accumulate
        NodeExecution.objects.create(
            node_id=node_id,
            output_data=result,
            timestamp=timezone.now()
        )
        
        # Clear from memory
        del result
```

#### **2. Lazy Loading**
```python
class LazyFlowContext:
    """
    Load flow data on-demand to reduce memory usage.
    """
    
    def get_node_result(self, node_id):
        # Load from database only when needed
        try:
            execution = NodeExecution.objects.get(node_id=node_id)
            return execution.output_data
        except NodeExecution.DoesNotExist:
            return None
```

#### **3. Garbage Collection**
```python
import gc

def cleanup_after_flow_execution():
    """
    Explicit cleanup after flow execution.
    """
    gc.collect()  # Force garbage collection
    
# Use in Celery task
@shared_task
def execute_flow_with_cleanup(flow_id):
    try:
        result = execute_flow(flow_id)
        return result
    finally:
        cleanup_after_flow_execution()
```

### **Expected Performance on 2GB RAM**

#### **Concurrent Flow Capacity**
```
Light Flows (< 5 nodes):      25-30 concurrent
Medium Flows (5-15 nodes):    15-20 concurrent  
Heavy Flows (> 15 nodes):     8-12 concurrent

Mixed Workload Average:       18-22 concurrent flows
```

#### **Throughput Estimates**
```
Quick Flows (< 30 sec):       ~100-150 flows/hour
Medium Flows (1-5 min):       ~40-60 flows/hour
Long Flows (5-30 min):        ~10-20 flows/hour

Total Daily Capacity:         ~2000-3000 flow executions
```

### **Monitoring & Alerting**

#### **Resource Alerts**
```python
class ResourceAlerts:
    """
    Alert system for resource constraints.
    """
    
    @staticmethod
    def check_memory_threshold():
        if ResourceMonitor.get_memory_usage() > 0.9:
            # Stop accepting new flows
            logger.warning("Memory usage critical - pausing new flows")
            return False
        return True
    
    @staticmethod
    def check_flow_queue_length():
        queue_length = get_celery_queue_length()
        if queue_length > 50:
            logger.warning(f"Flow queue backed up: {queue_length} pending")
```

### **Deployment Configuration**

#### **Celery Workers**
```bash
# Single worker optimized for 2GB RAM
celery -A edgesync worker \
    --pool=gevent \
    --concurrency=25 \
    --max-tasks-per-child=100 \
    --loglevel=info
```

#### **Redis Configuration**
```redis
# Optimized for low memory
maxmemory 100mb
maxmemory-policy allkeys-lru
save ""  # Disable persistence to save memory
```

This Phase 3 implementation provides efficient background processing within your 2GB RAM constraint while maintaining good performance for IoT data flows.
