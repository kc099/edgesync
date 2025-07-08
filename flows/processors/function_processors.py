from typing import Dict, Any, List, Optional
from collections import deque
from .base_processor import BaseProcessor, ValidationError, ExecutionError
import statistics
import json
from datetime import datetime

class MovingAverageProcessor(BaseProcessor):
    """
    Processor for moving average calculation.
    
    Maintains a sliding window of values and calculates the average.
    Configuration:
    - windowSize: Number of values to include in average (default: 10)
    - resetOnStart: Whether to reset the window on flow start
    """
    
    def __init__(self, node_config: Dict[str, Any], flow_context: Optional[Dict[str, Any]] = None):
        super().__init__(node_config, flow_context)
        self.value_window = deque()
        self.window_size = self.get_node_property('windowSize', 10)
    
    def validate_config(self) -> None:
        super().validate_config()
        
        window_size = self.get_node_property('windowSize', 10)
        if not isinstance(window_size, int) or window_size <= 0:
            raise ValidationError("Moving average window size must be a positive integer")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute moving average calculation.
        
        Args:
            input_data: Should contain 'output' or 'value' key with numeric value
            
        Returns:
            Dict with moving average result
        """
        # Get input value
        value = input_data.get('output') or input_data.get('value')
        
        if value is None:
            raise ExecutionError("No value provided for moving average calculation")
        
        # Convert to float
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            raise ExecutionError(f"Invalid numeric value for moving average: {value}")
        
        # Add to window
        self.value_window.append(numeric_value)
        
        # Maintain window size
        if len(self.value_window) > self.window_size:
            self.value_window.popleft()
        
        # Calculate moving average
        current_average = sum(self.value_window) / len(self.value_window)
        
        # Store in flow context
        self.set_flow_variable(f'moving_avg_{self.node_id}', current_average)
        
        return {
            'output': current_average,
            'current_value': numeric_value,
            'window_size': len(self.value_window),
            'window_full': len(self.value_window) == self.window_size,
            'min_in_window': min(self.value_window),
            'max_in_window': max(self.value_window)
        }
    
    def reset_window(self) -> None:
        """Reset the moving average window."""
        self.value_window.clear()

class MinMaxProcessor(BaseProcessor):
    """
    Processor for min/max calculation.
    
    Tracks minimum and maximum values over time.
    Configuration:
    - mode: 'min', 'max', or 'both' (default: 'both')
    - resetOnStart: Whether to reset values on flow start
    - windowSize: Optional window size for rolling min/max
    """
    
    def __init__(self, node_config: Dict[str, Any], flow_context: Optional[Dict[str, Any]] = None):
        super().__init__(node_config, flow_context)
        self.min_value = None
        self.max_value = None
        self.value_history = deque()
        self.window_size = self.get_node_property('windowSize')
    
    def validate_config(self) -> None:
        super().validate_config()
        
        mode = self.get_node_property('mode', 'both')
        if mode not in ['min', 'max', 'both']:
            raise ValidationError("MinMax mode must be 'min', 'max', or 'both'")
        
        window_size = self.get_node_property('windowSize')
        if window_size is not None and (not isinstance(window_size, int) or window_size <= 0):
            raise ValidationError("MinMax window size must be a positive integer")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute min/max calculation.
        
        Args:
            input_data: Should contain 'output' or 'value' key with numeric value
            
        Returns:
            Dict with min/max results
        """
        # Get input value
        value = input_data.get('output') or input_data.get('value')
        
        if value is None:
            raise ExecutionError("No value provided for min/max calculation")
        
        # Convert to float
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            raise ExecutionError(f"Invalid numeric value for min/max: {value}")
        
        # Handle windowed min/max
        if self.window_size:
            self.value_history.append(numeric_value)
            if len(self.value_history) > self.window_size:
                self.value_history.popleft()
            
            current_min = min(self.value_history)
            current_max = max(self.value_history)
        else:
            # Global min/max
            if self.min_value is None or numeric_value < self.min_value:
                self.min_value = numeric_value
            if self.max_value is None or numeric_value > self.max_value:
                self.max_value = numeric_value
                
            current_min = self.min_value
            current_max = self.max_value
        
        # Determine output based on mode
        mode = self.get_node_property('mode', 'both')
        
        if mode == 'min':
            output = current_min
        elif mode == 'max':
            output = current_max
        else:  # both
            output = {'min': current_min, 'max': current_max}
        
        # Store in flow context
        self.set_flow_variable(f'minmax_{self.node_id}', output)
        
        return {
            'output': output,
            'current_value': numeric_value,
            'min': current_min,
            'max': current_max,
            'range': current_max - current_min if current_max is not None and current_min is not None else 0
        }
    
    def reset_values(self) -> None:
        """Reset min/max values."""
        self.min_value = None
        self.max_value = None
        self.value_history.clear()

class CommentProcessor(BaseProcessor):
    """
    Processor for comment nodes.
    
    Passes through input data unchanged while providing documentation.
    Configuration:
    - comment: Comment text content
    """
    
    def validate_config(self) -> None:
        super().validate_config()
        # Comments don't require specific validation
        pass
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute comment node (pass-through).
        
        Args:
            input_data: Input data to pass through
            
        Returns:
            Input data unchanged
        """
        comment_text = self.get_node_property('comment', '')
        
        # Store comment in flow context for debugging
        self.set_flow_variable(f'comment_{self.node_id}', comment_text)
        
        # Pass through all input data unchanged
        return input_data

class DebugProcessor(BaseProcessor):
    """
    Processor for debug nodes.
    
    Logs input data and passes it through for debugging purposes.
    Configuration:
    - logLevel: 'info', 'debug', 'warning', 'error' (default: 'info')
    - logMessage: Optional custom log message
    """
    
    def validate_config(self) -> None:
        super().validate_config()
        
        log_level = self.get_node_property('logLevel', 'info')
        if log_level not in ['info', 'debug', 'warning', 'error']:
            raise ValidationError("Debug log level must be 'info', 'debug', 'warning', or 'error'")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute debug node.
        
        Args:
            input_data: Input data to log and pass through
            
        Returns:
            Input data with debug information added
        """
        import logging
        
        logger = logging.getLogger(f'flow.debug.{self.node_id}')
        
        # Get configuration
        log_level = self.get_node_property('logLevel', 'info')
        log_message = self.get_node_property('logMessage', f'Debug node {self.node_id}')
        
        # Create debug info
        debug_info = {
            'node_id': self.node_id,
            'timestamp': datetime.now().isoformat(),
            'input_data': input_data,
            'message': log_message
        }
        
        # Log based on configured level
        log_data = f"{log_message}: {json.dumps(input_data, indent=2)}"
        
        if log_level == 'debug':
            logger.debug(log_data)
        elif log_level == 'warning':
            logger.warning(log_data)
        elif log_level == 'error':
            logger.error(log_data)
        else:  # info
            logger.info(log_data)
        
        # Store debug info in flow context
        debug_history = self.get_flow_variable('debug_history', [])
        debug_history.append(debug_info)
        self.set_flow_variable('debug_history', debug_history)
        
        # Add debug information to output
        result = input_data.copy()
        result['debug_info'] = debug_info
        
        return result

class CustomFunctionProcessor(BaseProcessor):
    """
    Processor for custom Python code execution.
    
    WARNING: This processor can execute arbitrary Python code.
    Should be used with caution and proper security measures.
    
    Configuration:
    - code: Python code to execute
    - allowedModules: List of allowed modules to import
    """
    
    def validate_config(self) -> None:
        super().validate_config()
        
        code = self.get_node_property('code')
        if not code:
            raise ValidationError("Custom function code is required")
        
        # Basic security check - prevent dangerous imports
        dangerous_keywords = ['import os', 'import sys', 'import subprocess', '__import__', 'exec', 'eval']
        code_lower = code.lower()
        
        for keyword in dangerous_keywords:
            if keyword in code_lower:
                raise ValidationError(f"Dangerous keyword '{keyword}' not allowed in custom function")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute custom Python code.
        
        Args:
            input_data: Input data available to the custom function
            
        Returns:
            Dict with custom function result
        """
        code = self.get_node_property('code')
        
        # Prepare execution context
        context = {
            'input': input_data,
            'math': __import__('math'),
            'statistics': __import__('statistics'),
            'json': __import__('json'),
            'datetime': __import__('datetime'),
            'result': None  # Function should set this
        }
        
        try:
            # Execute the custom code
            exec(code, context)
            
            # Get result
            result = context.get('result')
            if result is None:
                raise ExecutionError("Custom function must set 'result' variable")
            
            # Store result in flow context
            self.set_flow_variable(f'custom_{self.node_id}', result)
            
            return {
                'output': result,
                'execution_time': self.get_execution_duration_ms()
            }
            
        except Exception as e:
            raise ExecutionError(f"Custom function execution failed: {str(e)}")
