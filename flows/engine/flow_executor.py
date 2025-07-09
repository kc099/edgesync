from typing import Dict, Any, Optional, List, Callable
import logging
from datetime import datetime

from .dependency_resolver import DependencyResolver, CircularDependencyError
from .node_scheduler import NodeScheduler, ExecutionStrategy
from .execution_context import ExecutionContext, ExecutionStatus
from ..models import FlowDiagram, FlowExecution, NodeExecution
from django.utils import timezone

logger = logging.getLogger(__name__)

class FlowExecutionError(Exception):
    """Raised when flow execution fails."""
    pass

class FlowExecutor:
    """
    Main flow executor that orchestrates the execution of a flow diagram.
    
    This class coordinates dependency resolution, node scheduling, and execution
    monitoring for a complete flow execution.
    """
    
    def __init__(self, 
                 flow_diagram: FlowDiagram,
                 execution_strategy: ExecutionStrategy = ExecutionStrategy.HYBRID,
                 max_workers: int = 4):
        """
        Initialize the flow executor.
        
        Args:
            flow_diagram: FlowDiagram instance to execute
            execution_strategy: Strategy for node execution
            max_workers: Maximum number of worker threads
        """
        self.flow_diagram = flow_diagram
        self.execution_strategy = execution_strategy
        self.max_workers = max_workers
        
        # Validate flow diagram
        if not flow_diagram.nodes or not isinstance(flow_diagram.nodes, list):
            raise FlowExecutionError("Flow diagram must have nodes")
        
        self.nodes = {node['id']: node for node in flow_diagram.nodes}
        self.edges = flow_diagram.edges or []
        
        # Initialize components
        self.dependency_resolver = None
        self.node_scheduler = None
        self.execution_context = None
        self.flow_execution = None
        
        # Event callbacks
        self.on_execution_start: Optional[Callable[[str], None]] = None
        self.on_execution_complete: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.on_execution_error: Optional[Callable[[str, Exception], None]] = None
        self.on_node_start: Optional[Callable[[str, str], None]] = None  # (execution_id, node_id)
        self.on_node_complete: Optional[Callable[[str, str, Dict[str, Any]], None]] = None
        self.on_node_error: Optional[Callable[[str, str, Exception], None]] = None
    
    def execute(self, 
                trigger_data: Optional[Dict[str, Any]] = None,
                execution_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the flow diagram.
        
        Args:
            trigger_data: Optional data that triggered the execution
            execution_id: Optional custom execution ID
            
        Returns:
            Dictionary with execution results
            
        Raises:
            FlowExecutionError: If execution fails
        """
        try:
            # Create database record for this execution
            self.flow_execution = FlowExecution.objects.create(
                flow=self.flow_diagram,
                status='running'
            )
            
            execution_id = execution_id or str(self.flow_execution.id)
            
            logger.info(f"Starting execution of flow {self.flow_diagram.name} (ID: {execution_id})")
            
            # Initialize execution context
            self.execution_context = ExecutionContext(
                flow_id=str(self.flow_diagram.uuid),
                execution_id=execution_id
            )
            
            # Add trigger data to context if provided
            if trigger_data:
                for key, value in trigger_data.items():
                    self.execution_context.set_variable(f'trigger_{key}', value)
            
            # Fire execution start callback
            if self.on_execution_start:
                self.on_execution_start(execution_id)
            
            # Step 1: Resolve dependencies
            logger.info("Resolving flow dependencies")
            self.dependency_resolver = DependencyResolver(list(self.nodes.values()), self.edges)
            execution_levels = self.dependency_resolver.resolve_dependencies()
            
            logger.info(f"Dependency resolution complete: {len(execution_levels)} execution levels")
            
            # Step 2: Create node scheduler
            self.node_scheduler = NodeScheduler(
                execution_levels=execution_levels,
                nodes=self.nodes,
                dependency_graph=self.dependency_resolver.reverse_graph,
                execution_context=self.execution_context,
                strategy=self.execution_strategy,
                max_workers=self.max_workers
            )
            
            # Set up node event callbacks
            self.node_scheduler.on_node_start = lambda node_id: self._on_node_start(node_id)
            self.node_scheduler.on_node_complete = lambda node_id, result: self._on_node_complete(node_id, result)
            self.node_scheduler.on_node_error = lambda node_id, error: self._on_node_error(node_id, error)
            self.node_scheduler.on_level_complete = lambda level_idx, nodes: self._on_level_complete(level_idx, nodes)
            
            # Step 3: Execute the flow
            logger.info("Starting flow execution")
            execution_results = self.node_scheduler.execute_flow()
            
            # Step 4: Update database record
            self.flow_execution.status = 'completed'
            self.flow_execution.completed_at = timezone.now()
            self.flow_execution.result = execution_results['execution_summary']
            self.flow_execution.save()
            
            # Fire execution complete callback
            if self.on_execution_complete:
                self.on_execution_complete(execution_id, execution_results)
            
            logger.info(f"Flow execution completed successfully (ID: {execution_id})")
            
            return {
                'success': True,
                'execution_id': execution_id,
                'flow_id': str(self.flow_diagram.uuid),
                'execution_results': execution_results,
                'dependency_info': self.dependency_resolver.get_dependency_summary()
            }
            
        except CircularDependencyError as e:
            error_msg = f"Circular dependency detected: {e}"
            logger.error(error_msg)
            self._handle_execution_error(error_msg, e)
            raise FlowExecutionError(error_msg) from e
            
        except Exception as e:
            error_msg = f"Flow execution failed: {e}"
            logger.error(error_msg)
            self._handle_execution_error(error_msg, e)
            raise FlowExecutionError(error_msg) from e
    
    def _handle_execution_error(self, error_msg: str, exception: Exception) -> None:
        """
        Handle execution errors by updating database and firing callbacks.
        
        Args:
            error_msg: Error message
            exception: The exception that occurred
        """
        # Update execution context
        if self.execution_context:
            self.execution_context.complete_execution(success=False, error=error_msg)
        
        # Update database record
        if self.flow_execution:
            self.flow_execution.status = 'failed'
            self.flow_execution.completed_at = timezone.now()
            self.flow_execution.error_message = error_msg
            self.flow_execution.save()
        
        # Fire execution error callback
        if self.on_execution_error:
            execution_id = self.execution_context.execution_id if self.execution_context else 'unknown'
            self.on_execution_error(execution_id, exception)
    
    def _on_node_start(self, node_id: str) -> None:
        """
        Handle node start event.
        
        Args:
            node_id: ID of the node that started
        """
        logger.debug(f"Node {node_id} started")
        
        # Create NodeExecution record
        NodeExecution.objects.create(
            flow_execution=self.flow_execution,
            node_id=node_id,
            status='running'
        )
        
        # Fire callback
        if self.on_node_start:
            self.on_node_start(self.execution_context.execution_id, node_id)
    
    def _on_node_complete(self, node_id: str, result: Dict[str, Any]) -> None:
        """
        Handle node completion event.
        
        Args:
            node_id: ID of the node that completed
            result: Execution result
        """
        logger.debug(f"Node {node_id} completed")
        
        # Update NodeExecution record
        try:
            node_execution = NodeExecution.objects.get(
                flow_execution=self.flow_execution,
                node_id=node_id
            )
            node_execution.status = 'completed'
            node_execution.executed_at = timezone.now()
            node_execution.output_data = result
            node_execution.duration_ms = int(result.get('execution_time_ms', 0))
            node_execution.save()
        except NodeExecution.DoesNotExist:
            logger.warning(f"NodeExecution record not found for node {node_id}")

        # Store node output for dashboard widgets
        try:
            from ..models import FlowNodeOutput
            FlowNodeOutput.objects.create(
                flow_execution=self.flow_execution,
                node_id=node_id,
                output_data=result
            )
            logger.debug(f"Stored output for node {node_id} for dashboard widgets")
        except Exception as e:
            logger.error(f"Failed to store node output for {node_id}: {e}")
        
        # Fire callback
        if self.on_node_complete:
            self.on_node_complete(self.execution_context.execution_id, node_id, result)
    
    def _on_node_error(self, node_id: str, error: Exception) -> None:
        """
        Handle node error event.
        
        Args:
            node_id: ID of the node that failed
            error: The exception that occurred
        """
        logger.error(f"Node {node_id} failed: {error}")
        
        # Update NodeExecution record
        try:
            node_execution = NodeExecution.objects.get(
                flow_execution=self.flow_execution,
                node_id=node_id
            )
            node_execution.status = 'failed'
            node_execution.executed_at = timezone.now()
            node_execution.output_data = {'error': str(error)}
            node_execution.save()
        except NodeExecution.DoesNotExist:
            logger.warning(f"NodeExecution record not found for node {node_id}")
        
        # Fire callback
        if self.on_node_error:
            self.on_node_error(self.execution_context.execution_id, node_id, error)
    
    def _on_level_complete(self, level_idx: int, nodes: List[str]) -> None:
        """
        Handle execution level completion.
        
        Args:
            level_idx: Index of the completed level
            nodes: List of nodes in the completed level
        """
        logger.info(f"Execution level {level_idx} completed with {len(nodes)} nodes")
    
    def pause_execution(self) -> bool:
        """
        Pause the current execution.
        
        Returns:
            True if execution was paused, False if not running
        """
        if self.node_scheduler and self.execution_context:
            if self.execution_context.is_running():
                self.node_scheduler.pause_execution()
                return True
        return False
    
    def resume_execution(self) -> bool:
        """
        Resume the paused execution.
        
        Returns:
            True if execution was resumed, False if not paused
        """
        if self.node_scheduler and self.execution_context:
            if self.execution_context.status == ExecutionStatus.PAUSED:
                self.node_scheduler.resume_execution()
                return True
        return False
    
    def stop_execution(self, reason: str = "User requested stop") -> bool:
        """
        Stop the current execution.
        
        Args:
            reason: Reason for stopping
            
        Returns:
            True if execution was stopped, False if not running
        """
        if self.node_scheduler and self.execution_context:
            if self.execution_context.is_running():
                self.node_scheduler.stop_execution(reason)
                
                # Update database record
                if self.flow_execution:
                    self.flow_execution.status = 'stopped'
                    self.flow_execution.completed_at = timezone.now()
                    self.flow_execution.error_message = reason
                    self.flow_execution.save()
                
                return True
        return False
    
    def get_execution_status(self) -> Dict[str, Any]:
        """
        Get the current execution status.
        
        Returns:
            Dictionary with execution status information
        """
        if not self.execution_context:
            return {'status': 'not_started'}
        
        summary = self.execution_context.get_execution_summary()
        
        # Add dependency information if available
        if self.dependency_resolver:
            summary['dependency_info'] = self.dependency_resolver.get_dependency_summary()
        
        return summary
    
    def get_node_status(self, node_id: str) -> Dict[str, Any]:
        """
        Get the status of a specific node.
        
        Args:
            node_id: ID of the node to check
            
        Returns:
            Dictionary with node status information
        """
        if not self.execution_context:
            return {'status': 'not_started'}
        
        status = self.execution_context.get_node_status(node_id)
        result = self.execution_context.get_node_result(node_id)
        
        return {
            'node_id': node_id,
            'status': status.value,
            'result': result,
            'can_execute': self.execution_context.can_execute_node(
                node_id, 
                self.dependency_resolver.reverse_graph if self.dependency_resolver else {}
            )
        }
    
    @classmethod
    def create_and_execute(cls, 
                          flow_diagram: FlowDiagram,
                          trigger_data: Optional[Dict[str, Any]] = None,
                          execution_strategy: ExecutionStrategy = ExecutionStrategy.HYBRID,
                          max_workers: int = 4) -> Dict[str, Any]:
        """
        Factory method to create and execute a flow in one call.
        
        Args:
            flow_diagram: FlowDiagram instance to execute
            trigger_data: Optional trigger data
            execution_strategy: Execution strategy to use
            max_workers: Maximum number of worker threads
            
        Returns:
            Dictionary with execution results
        """
        executor = cls(
            flow_diagram=flow_diagram,
            execution_strategy=execution_strategy,
            max_workers=max_workers
        )
        
        return executor.execute(trigger_data=trigger_data)
