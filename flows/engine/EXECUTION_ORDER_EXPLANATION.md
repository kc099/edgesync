# Flow Execution Engine - Dependency Resolution & Execution Order

## Overview

The Flow Execution Engine implements a sophisticated dependency resolution system that analyzes the flow graph to determine the optimal execution order for nodes. This document explains the algorithms and strategies used to handle node dependencies and execution sequencing.

## Core Concepts

### 1. Flow Graph Structure

```json
{
  "nodes": [
    {
      "id": "node-1",
      "type": "input",
      "data": { "nodeType": "button" },
      "position": { "x": 100, "y": 100 }
    },
    {
      "id": "node-2",
      "type": "function",
      "data": { "nodeType": "moving-average" },
      "position": { "x": 300, "y": 100 }
    }
  ],
  "edges": [
    {
      "id": "edge-1",
      "source": "node-1",
      "target": "node-2",
      "sourceHandle": "output",
      "targetHandle": "input"
    }
  ]
}
```

### 2. Dependency Types

#### **Data Dependencies**
- **Direct**: Node B depends on output from Node A
- **Indirect**: Node C depends on Node B, which depends on Node A
- **Conditional**: Node execution depends on conditional logic

#### **Execution Dependencies**
- **Sequential**: Nodes must execute in specific order
- **Parallel**: Independent nodes can execute simultaneously
- **Cyclical**: Handling feedback loops and circular dependencies

## Dependency Resolution Algorithm

### 1. Graph Analysis Phase

```python
def analyze_flow_graph(nodes, edges):
    """
    Analyze flow graph to build dependency relationships.
    
    Returns:
    - dependency_graph: Dict mapping node_id -> [dependent_nodes]
    - reverse_graph: Dict mapping node_id -> [prerequisite_nodes]
    - execution_levels: List of lists containing nodes at each level
    """
```

#### **Step 1: Build Adjacency Lists**

```python
# Forward dependencies (who depends on this node)
dependency_graph = {
    "node-1": ["node-2", "node-3"],
    "node-2": ["node-4"],
    "node-3": ["node-4"],
    "node-4": []
}

# Reverse dependencies (what this node depends on)
reverse_graph = {
    "node-1": [],
    "node-2": ["node-1"],
    "node-3": ["node-1"], 
    "node-4": ["node-2", "node-3"]
}
```

#### **Step 2: Detect Cycles**

```python
def detect_cycles(graph):
    """
    Use DFS to detect cycles in the flow graph.
    
    Returns:
    - has_cycles: Boolean indicating if cycles exist
    - cycle_nodes: List of nodes involved in cycles
    """
    visited = set()
    rec_stack = set()
    
    def dfs(node):
        if node in rec_stack:
            return True  # Cycle detected
        if node in visited:
            return False
            
        visited.add(node)
        rec_stack.add(node)
        
        for neighbor in graph.get(node, []):
            if dfs(neighbor):
                return True
                
        rec_stack.remove(node)
        return False
```

### 2. Topological Sorting

#### **Kahn's Algorithm Implementation**

```python
def topological_sort(nodes, edges):
    """
    Perform topological sorting to determine execution order.
    
    Returns:
    - execution_levels: List of lists, each containing nodes that can execute in parallel
    - total_order: Flattened list of all nodes in execution order
    """
    # Calculate in-degrees for each node
    in_degree = {node_id: 0 for node_id in nodes}
    
    for edge in edges:
        in_degree[edge['target']] += 1
    
    # Initialize queue with nodes having no dependencies
    queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
    execution_levels = []
    
    while queue:
        current_level = queue.copy()
        queue.clear()
        execution_levels.append(current_level)
        
        for node_id in current_level:
            # Process all dependent nodes
            for edge in edges:
                if edge['source'] == node_id:
                    target = edge['target']
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append(target)
    
    return execution_levels
```

### 3. Execution Level Grouping

```python
Example execution levels:
Level 0: ["input-1", "input-2"]           # Independent input nodes
Level 1: ["function-1", "function-2"]     # Depend on Level 0
Level 2: ["function-3"]                   # Depends on both Level 1 nodes
Level 3: ["output-1", "output-2"]         # Final output nodes
```

## Execution Strategies

### 1. Sequential Execution

```python
def execute_sequential(execution_levels, processors):
    """
    Execute nodes level by level, waiting for each level to complete.
    
    Advantages:
    - Simple and predictable
    - Easy debugging
    - Resource-efficient
    
    Disadvantages:
    - Slower execution
    - Doesn't utilize parallelism
    """
    for level in execution_levels:
        for node_id in level:
            processor = processors[node_id]
            result = processor.execute(input_data)
            store_result(node_id, result)
```

### 2. Parallel Execution

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def execute_parallel(execution_levels, processors):
    """
    Execute nodes within each level in parallel.
    
    Advantages:
    - Faster execution
    - Better resource utilization
    - Scalable
    
    Disadvantages:
    - Complex error handling
    - Resource contention
    - Debugging complexity
    """
    for level in execution_levels:
        tasks = []
        for node_id in level:
            processor = processors[node_id]
            task = asyncio.create_task(execute_node(processor, input_data))
            tasks.append(task)
        
        # Wait for all nodes in this level to complete
        results = await asyncio.gather(*tasks)
        
        # Store results for next level
        for node_id, result in zip(level, results):
            store_result(node_id, result)
```

### 3. Hybrid Execution

```python
def execute_hybrid(execution_levels, processors):
    """
    Combine sequential and parallel execution based on node types.
    
    Rules:
    - I/O operations (device, network): Parallel
    - CPU-intensive operations: Sequential
    - Critical path nodes: Sequential
    """
    for level in execution_levels:
        parallel_nodes = []
        sequential_nodes = []
        
        for node_id in level:
            processor = processors[node_id]
            if processor.supports_parallel():
                parallel_nodes.append(node_id)
            else:
                sequential_nodes.append(node_id)
        
        # Execute parallel nodes concurrently
        if parallel_nodes:
            execute_parallel_batch(parallel_nodes, processors)
        
        # Execute sequential nodes one by one
        for node_id in sequential_nodes:
            execute_sequential_node(node_id, processors[node_id])
```

## Special Cases & Edge Conditions

### 1. Circular Dependencies

```python
def handle_circular_dependencies(cycle_nodes):
    """
    Handle feedback loops in the flow graph.
    
    Strategies:
    1. Break cycles by introducing delays
    2. Use previous execution values
    3. Implement iterative solving
    """
    # Strategy 1: Delay-based cycle breaking
    for node_id in cycle_nodes:
        if is_delay_node(node_id):
            # Use previous value as input
            input_data = get_previous_value(node_id)
            break
    
    # Strategy 2: Iterative solving
    max_iterations = 100
    tolerance = 1e-6
    
    for iteration in range(max_iterations):
        old_values = get_cycle_values(cycle_nodes)
        execute_cycle_nodes(cycle_nodes)
        new_values = get_cycle_values(cycle_nodes)
        
        if converged(old_values, new_values, tolerance):
            break
```

### 2. Conditional Execution

```python
def handle_conditional_execution(node_id, condition_result):
    """
    Handle nodes that should only execute under certain conditions.
    
    Examples:
    - If/Then/Else logic
    - Switch statements
    - Error handling branches
    """
    if condition_result:
        execute_node(node_id)
    else:
        # Skip execution but propagate null/default values
        propagate_default_values(node_id)
```

### 3. Error Propagation

```python
def handle_execution_errors(node_id, error):
    """
    Handle errors during node execution.
    
    Strategies:
    1. Fail-fast: Stop entire flow execution
    2. Isolate: Continue with other branches
    3. Retry: Attempt execution again
    4. Default: Use fallback values
    """
    error_policy = get_error_policy(node_id)
    
    if error_policy == 'fail_fast':
        raise FlowExecutionError(f"Node {node_id} failed: {error}")
    
    elif error_policy == 'isolate':
        mark_branch_as_failed(node_id)
        continue_with_other_branches()
    
    elif error_policy == 'retry':
        for attempt in range(max_retries):
            try:
                return execute_node(node_id)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                sleep(retry_delay)
    
    elif error_policy == 'default':
        return get_default_value(node_id)
```

## Performance Optimizations

### 1. Caching Strategy

```python
def implement_caching(node_id, input_data):
    """
    Cache node execution results to avoid redundant calculations.
    
    Strategies:
    - Input-based caching: Cache based on input hash
    - Time-based caching: Cache for specific duration
    - Dependency-based caching: Invalidate when dependencies change
    """
    cache_key = generate_cache_key(node_id, input_data)
    
    if cache_key in execution_cache:
        return execution_cache[cache_key]
    
    result = execute_node(node_id, input_data)
    execution_cache[cache_key] = result
    
    return result
```

### 2. Critical Path Analysis

```python
def analyze_critical_path(execution_levels):
    """
    Identify the critical path through the flow graph.
    
    Critical path determines minimum execution time.
    Optimize critical path nodes for better performance.
    """
    # Calculate execution times for each path
    paths = find_all_paths(execution_levels)
    critical_path = max(paths, key=lambda path: calculate_path_time(path))
    
    # Optimize critical path nodes
    for node_id in critical_path:
        optimize_node_execution(node_id)
```

## Implementation Architecture

```python
class FlowExecutor:
    def __init__(self, flow_diagram):
        self.nodes = flow_diagram.nodes
        self.edges = flow_diagram.edges
        self.execution_levels = self._analyze_dependencies()
        self.processors = self._create_processors()
    
    def execute(self):
        """Main execution entry point."""
        return self._execute_flow()
    
    def _analyze_dependencies(self):
        """Analyze flow graph and determine execution order."""
        return topological_sort(self.nodes, self.edges)
    
    def _create_processors(self):
        """Create processor instances for each node."""
        return {node['id']: ProcessorFactory.create_processor(node) 
                for node in self.nodes}
    
    def _execute_flow(self):
        """Execute the flow using determined execution order."""
        if self.execution_strategy == 'sequential':
            return self._execute_sequential()
        elif self.execution_strategy == 'parallel':
            return self._execute_parallel()
        else:
            return self._execute_hybrid()
```

## Testing & Validation

### 1. Dependency Resolution Tests

```python
def test_dependency_resolution():
    """Test various dependency scenarios."""
    # Test simple linear flow
    # Test parallel branches
    # Test diamond dependency pattern
    # Test circular dependencies
    # Test conditional execution
```

### 2. Performance Benchmarks

```python
def benchmark_execution_strategies():
    """Compare performance of different execution strategies."""
    # Sequential vs Parallel
    # Memory usage
    # Execution time
    # Error rate
```

This dependency resolution and execution order system provides a robust foundation for handling complex flow graphs with various dependency patterns while maintaining optimal performance and reliability.
