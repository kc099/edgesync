from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ProcessorError(Exception):
    """Base exception for processor errors"""
    pass

class ValidationError(ProcessorError):
    """Raised when node configuration is invalid"""
    pass

class ExecutionError(ProcessorError):
    """Raised when node execution fails"""
    pass

class BaseProcessor(ABC):
    """
    Abstract base class for all node processors.
    
    Each node type in the flow editor should have a corresponding processor
    that inherits from this class and implements the execute method.
    """
    
    def __init__(self, node_config: Dict[str, Any], flow_context: Optional[Dict[str, Any]] = None):
        """
        Initialize the processor with node configuration.
        
        Args:
            node_config: Node configuration from React Flow
            flow_context: Optional flow-level context and variables
        """
        self.node_config = node_config
        self.flow_context = flow_context or {}
        self.node_id = node_config.get('id')
        self.node_type = node_config.get('type')
        self.node_data = node_config.get('data', {})
        self.execution_start_time = None
        self.execution_end_time = None
        
        # Validate configuration on initialization
        self.validate_config()
    
    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the node with given input data.
        
        Args:
            input_data: Data received from input connections
            
        Returns:
            Dict containing output data to pass to connected nodes
            
        Raises:
            ExecutionError: If execution fails
        """
        pass
    
    def validate_config(self) -> None:
        """
        Validate the node configuration.
        
        Raises:
            ValidationError: If configuration is invalid
        """
        if not self.node_id:
            raise ValidationError("Node ID is required")
        
        if not self.node_type:
            raise ValidationError("Node type is required")
    
    def get_node_property(self, key: str, default: Any = None) -> Any:
        """
        Get a property from the node data configuration.
        
        Args:
            key: Property key
            default: Default value if key not found
            
        Returns:
            Property value or default
        """
        return self.node_data.get(key, default)
    
    def set_flow_variable(self, key: str, value: Any) -> None:
        """
        Set a flow-level variable that can be accessed by other nodes.
        
        Args:
            key: Variable name
            value: Variable value
        """
        if 'variables' not in self.flow_context:
            self.flow_context['variables'] = {}
        self.flow_context['variables'][key] = value
    
    def get_flow_variable(self, key: str, default: Any = None) -> Any:
        """
        Get a flow-level variable.
        
        Args:
            key: Variable name
            default: Default value if variable not found
            
        Returns:
            Variable value or default
        """
        return self.flow_context.get('variables', {}).get(key, default)
    
    def log_execution_start(self) -> None:
        """Log the start of node execution."""
        self.execution_start_time = datetime.now()
        logger.info(f"Starting execution of node {self.node_id} ({self.node_type})")
    
    def log_execution_end(self, success: bool = True, error: Optional[str] = None) -> None:
        """Log the end of node execution."""
        self.execution_end_time = datetime.now()
        duration = (self.execution_end_time - self.execution_start_time).total_seconds() * 1000
        
        if success:
            logger.info(f"Completed execution of node {self.node_id} in {duration:.2f}ms")
        else:
            logger.error(f"Failed execution of node {self.node_id} after {duration:.2f}ms: {error}")
    
    def get_execution_duration_ms(self) -> float:
        """
        Get the execution duration in milliseconds.
        
        Returns:
            Duration in milliseconds, or 0 if not executed
        """
        if self.execution_start_time and self.execution_end_time:
            return (self.execution_end_time - self.execution_start_time).total_seconds() * 1000
        return 0
    
    def safe_execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the node with error handling and logging.
        
        Args:
            input_data: Input data for the node
            
        Returns:
            Output data from the node
            
        Raises:
            ExecutionError: If execution fails
        """
        try:
            self.log_execution_start()
            result = self.execute(input_data)
            self.log_execution_end(success=True)
            return result
        except Exception as e:
            error_msg = f"Execution failed: {str(e)}"
            self.log_execution_end(success=False, error=error_msg)
            raise ExecutionError(error_msg) from e
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self.node_id}, type={self.node_type})"
