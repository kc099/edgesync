from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import threading
import uuid

class ExecutionStatus(Enum):
    """Execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"
    PAUSED = "paused"

class ExecutionContext:
    """
    Manages the execution context for a flow run.
    
    This class provides thread-safe access to flow execution state,
    node results, and shared variables.
    """
    
    def __init__(self, flow_id: str, execution_id: Optional[str] = None):
        """
        Initialize execution context.
        
        Args:
            flow_id: ID of the flow being executed
            execution_id: Optional execution ID, generates UUID if not provided
        """
        self.flow_id = flow_id
        self.execution_id = execution_id or str(uuid.uuid4())
        self.status = ExecutionStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        
        # Thread-safe storage
        self._lock = threading.RLock()
        self._node_results = {}  # node_id -> execution result
        self._node_status = {}   # node_id -> execution status
        self._variables = {}     # flow-level variables
        self._execution_log = [] # execution log entries
        self._metrics = {        # execution metrics
            'nodes_executed': 0,
            'nodes_failed': 0,
            'total_execution_time': 0,
            'average_node_time': 0
        }
    
    def start_execution(self) -> None:
        """
        Mark the execution as started.
        """
        with self._lock:
            self.status = ExecutionStatus.RUNNING
            self.started_at = datetime.now()
            self._log_event('execution_started', {'execution_id': self.execution_id})
    
    def complete_execution(self, success: bool = True, error: Optional[str] = None) -> None:
        """
        Mark the execution as completed.
        
        Args:
            success: Whether execution completed successfully
            error: Error message if execution failed
        """
        with self._lock:
            self.completed_at = datetime.now()
            self.error_message = error
            
            if success and not error:
                self.status = ExecutionStatus.COMPLETED
            else:
                self.status = ExecutionStatus.FAILED
            
            # Calculate final metrics
            if self.started_at and self.completed_at:
                self._metrics['total_execution_time'] = (
                    self.completed_at - self.started_at
                ).total_seconds() * 1000  # milliseconds
            
            executed_nodes = sum(1 for status in self._node_status.values() 
                               if status == ExecutionStatus.COMPLETED)
            if executed_nodes > 0:
                self._metrics['average_node_time'] = (
                    self._metrics['total_execution_time'] / executed_nodes
                )
            
            self._log_event('execution_completed', {
                'success': success,
                'error': error,
                'metrics': self._metrics
            })
    
    def pause_execution(self) -> None:
        """
        Pause the execution.
        """
        with self._lock:
            if self.status == ExecutionStatus.RUNNING:
                self.status = ExecutionStatus.PAUSED
                self._log_event('execution_paused', {})
    
    def resume_execution(self) -> None:
        """
        Resume the execution.
        """
        with self._lock:
            if self.status == ExecutionStatus.PAUSED:
                self.status = ExecutionStatus.RUNNING
                self._log_event('execution_resumed', {})
    
    def stop_execution(self, reason: str = "User requested stop") -> None:
        """
        Stop the execution.
        
        Args:
            reason: Reason for stopping
        """
        with self._lock:
            self.status = ExecutionStatus.STOPPED
            self.completed_at = datetime.now()
            self.error_message = reason
            self._log_event('execution_stopped', {'reason': reason})
    
    def set_node_status(self, node_id: str, status: ExecutionStatus) -> None:
        """
        Set the execution status for a node.
        
        Args:
            node_id: Node ID
            status: Execution status
        """
        with self._lock:
            self._node_status[node_id] = status
            self._log_event('node_status_changed', {
                'node_id': node_id,
                'status': status.value
            })
    
    def get_node_status(self, node_id: str) -> ExecutionStatus:
        """
        Get the execution status for a node.
        
        Args:
            node_id: Node ID
            
        Returns:
            Execution status
        """
        with self._lock:
            return self._node_status.get(node_id, ExecutionStatus.PENDING)
    
    def set_node_result(self, node_id: str, result: Dict[str, Any]) -> None:
        """
        Store the execution result for a node.
        
        Args:
            node_id: Node ID
            result: Execution result
        """
        with self._lock:
            self._node_results[node_id] = {
                'result': result,
                'timestamp': datetime.now().isoformat(),
                'execution_id': self.execution_id
            }
            
            # Update metrics
            if self.get_node_status(node_id) == ExecutionStatus.COMPLETED:
                self._metrics['nodes_executed'] += 1
            elif self.get_node_status(node_id) == ExecutionStatus.FAILED:
                self._metrics['nodes_failed'] += 1
    
    def get_node_result(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the execution result for a node.
        
        Args:
            node_id: Node ID
            
        Returns:
            Execution result or None if not available
        """
        with self._lock:
            node_data = self._node_results.get(node_id)
            return node_data['result'] if node_data else None
    
    def get_node_input_data(self, node_id: str, dependency_graph: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        Get input data for a node based on its dependencies.
        
        Args:
            node_id: Node ID
            dependency_graph: Reverse dependency graph (node -> prerequisites)
            
        Returns:
            Combined input data from all prerequisite nodes
        """
        with self._lock:
            input_data = {}
            
            # Get results from all prerequisite nodes
            prerequisites = dependency_graph.get(node_id, [])
            
            for prereq_node in prerequisites:
                prereq_result = self.get_node_result(prereq_node)
                if prereq_result:
                    # Merge prerequisite results
                    if isinstance(prereq_result, dict):
                        input_data.update(prereq_result)
                    else:
                        # If result is not a dict, use the node ID as key
                        input_data[f'input_{prereq_node}'] = prereq_result
            
            return input_data
    
    def set_variable(self, key: str, value: Any) -> None:
        """
        Set a flow-level variable.
        
        Args:
            key: Variable name
            value: Variable value
        """
        with self._lock:
            self._variables[key] = value
            self._log_event('variable_set', {'key': key, 'value': value})
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """
        Get a flow-level variable.
        
        Args:
            key: Variable name
            default: Default value if variable not found
            
        Returns:
            Variable value or default
        """
        with self._lock:
            return self._variables.get(key, default)
    
    def get_all_variables(self) -> Dict[str, Any]:
        """
        Get all flow-level variables.
        
        Returns:
            Dictionary of all variables
        """
        with self._lock:
            return self._variables.copy()
    
    def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Log an execution event.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'execution_id': self.execution_id,
            'data': data
        }
        self._execution_log.append(log_entry)
        
        # Keep only the last 1000 log entries
        if len(self._execution_log) > 1000:
            self._execution_log = self._execution_log[-1000:]
    
    def get_execution_log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get execution log entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of log entries
        """
        with self._lock:
            if limit is None:
                return self._execution_log.copy()
            else:
                return self._execution_log[-limit:]
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Get execution summary information.
        
        Returns:
            Dictionary with execution summary
        """
        with self._lock:
            total_nodes = len(self._node_status)
            completed_nodes = sum(1 for status in self._node_status.values() 
                                if status == ExecutionStatus.COMPLETED)
            failed_nodes = sum(1 for status in self._node_status.values() 
                             if status == ExecutionStatus.FAILED)
            pending_nodes = sum(1 for status in self._node_status.values() 
                              if status == ExecutionStatus.PENDING)
            running_nodes = sum(1 for status in self._node_status.values() 
                              if status == ExecutionStatus.RUNNING)
            
            return {
                'execution_id': self.execution_id,
                'flow_id': self.flow_id,
                'status': self.status.value,
                'started_at': self.started_at.isoformat() if self.started_at else None,
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                'error_message': self.error_message,
                'node_counts': {
                    'total': total_nodes,
                    'completed': completed_nodes,
                    'failed': failed_nodes,
                    'pending': pending_nodes,
                    'running': running_nodes
                },
                'metrics': self._metrics.copy(),
                'variables_count': len(self._variables),
                'log_entries': len(self._execution_log)
            }
    
    def is_running(self) -> bool:
        """
        Check if execution is currently running.
        
        Returns:
            True if execution is running or paused
        """
        return self.status in [ExecutionStatus.RUNNING, ExecutionStatus.PAUSED]
    
    def is_completed(self) -> bool:
        """
        Check if execution is completed (successfully or with failure).
        
        Returns:
            True if execution is completed, failed, or stopped
        """
        return self.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.STOPPED]
    
    def can_execute_node(self, node_id: str, dependency_graph: Dict[str, List[str]]) -> bool:
        """
        Check if a node can be executed based on its dependencies.
        
        Args:
            node_id: Node ID to check
            dependency_graph: Reverse dependency graph
            
        Returns:
            True if node can be executed
        """
        with self._lock:
            # Check if execution is running
            if not self.is_running():
                return False
            
            # Check if node is already completed or running
            node_status = self.get_node_status(node_id)
            if node_status in [ExecutionStatus.COMPLETED, ExecutionStatus.RUNNING]:
                return False
            
            # Check if all prerequisites are completed
            prerequisites = dependency_graph.get(node_id, [])
            for prereq_node in prerequisites:
                prereq_status = self.get_node_status(prereq_node)
                if prereq_status != ExecutionStatus.COMPLETED:
                    return False
            
            return True
