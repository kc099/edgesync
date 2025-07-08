from typing import Dict, Any, Optional
from django.utils import timezone
from .base_processor import BaseProcessor, ValidationError, ExecutionError
from sensors.models import Device, SensorData
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from datetime import datetime

class DigitalOutputProcessor(BaseProcessor):
    """
    Processor for digital output nodes.
    
    Handles binary (on/off) output operations.
    Configuration:
    - outputPin: Pin number for output (optional)
    - invertLogic: Whether to invert the output logic
    - initialState: Initial output state (true/false)
    """
    
    def __init__(self, node_config: Dict[str, Any], flow_context: Optional[Dict[str, Any]] = None):
        super().__init__(node_config, flow_context)
        self.channel_layer = get_channel_layer()
        self.current_state = self.get_node_property('initialState', False)
    
    def validate_config(self) -> None:
        super().validate_config()
        
        output_pin = self.get_node_property('outputPin')
        if output_pin is not None and (not isinstance(output_pin, int) or output_pin < 0):
            raise ValidationError("Digital output pin must be a non-negative integer")
        
        initial_state = self.get_node_property('initialState', False)
        if not isinstance(initial_state, bool):
            raise ValidationError("Digital output initial state must be a boolean")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute digital output.
        
        Args:
            input_data: Should contain boolean value to output
            
        Returns:
            Dict with digital output result
        """
        # Get input value
        value = input_data.get('output') or input_data.get('value')
        
        if value is None:
            raise ExecutionError("No value provided for digital output")
        
        # Convert to boolean
        if isinstance(value, str):
            boolean_value = value.lower() in ['true', '1', 'on', 'yes', 'high']
        elif isinstance(value, (int, float)):
            boolean_value = value > 0
        else:
            boolean_value = bool(value)
        
        # Apply logic inversion if configured
        invert_logic = self.get_node_property('invertLogic', False)
        if invert_logic:
            boolean_value = not boolean_value
        
        # Update current state
        self.current_state = boolean_value
        
        # Send output command
        self._send_digital_output(boolean_value)
        
        # Store state in flow context
        self.set_flow_variable(f'digital_out_{self.node_id}', boolean_value)
        
        return {
            'output': boolean_value,
            'pin': self.get_node_property('outputPin'),
            'state': 'HIGH' if boolean_value else 'LOW',
            'timestamp': timezone.now().isoformat()
        }
    
    def _send_digital_output(self, value: bool) -> None:
        """
        Send digital output command.
        
        Args:
            value: Boolean value to output
        """
        try:
            # Prepare output command
            command = {
                'type': 'digital_output',
                'node_id': self.node_id,
                'pin': self.get_node_property('outputPin'),
                'value': value,
                'timestamp': timezone.now().isoformat()
            }
            
            # Send to flow execution group
            if self.channel_layer:
                async_to_sync(self.channel_layer.group_send)(
                    f'flow_execution_{self.flow_context.get("execution_id")}',
                    {
                        'type': 'digital_output',
                        'message': command
                    }
                )
            
        except Exception as e:
            raise ExecutionError(f"Failed to send digital output: {str(e)}")

class AnalogOutputProcessor(BaseProcessor):
    """
    Processor for analog output nodes.
    
    Handles continuous value output operations.
    Configuration:
    - outputPin: Pin number for output (optional)
    - minValue: Minimum output value (default: 0)
    - maxValue: Maximum output value (default: 255)
    - resolution: Output resolution in bits (default: 8)
    """
    
    def __init__(self, node_config: Dict[str, Any], flow_context: Optional[Dict[str, Any]] = None):
        super().__init__(node_config, flow_context)
        self.channel_layer = get_channel_layer()
        self.current_value = 0
    
    def validate_config(self) -> None:
        super().validate_config()
        
        output_pin = self.get_node_property('outputPin')
        if output_pin is not None and (not isinstance(output_pin, int) or output_pin < 0):
            raise ValidationError("Analog output pin must be a non-negative integer")
        
        min_value = self.get_node_property('minValue', 0)
        max_value = self.get_node_property('maxValue', 255)
        
        if min_value >= max_value:
            raise ValidationError("Analog output min value must be less than max value")
        
        resolution = self.get_node_property('resolution', 8)
        if not isinstance(resolution, int) or resolution < 1 or resolution > 16:
            raise ValidationError("Analog output resolution must be between 1 and 16 bits")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute analog output.
        
        Args:
            input_data: Should contain numeric value to output
            
        Returns:
            Dict with analog output result
        """
        # Get input value
        value = input_data.get('output') or input_data.get('value')
        
        if value is None:
            raise ExecutionError("No value provided for analog output")
        
        # Convert to numeric
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            raise ExecutionError(f"Invalid numeric value for analog output: {value}")
        
        # Apply bounds
        min_value = self.get_node_property('minValue', 0)
        max_value = self.get_node_property('maxValue', 255)
        
        constrained_value = max(min_value, min(max_value, numeric_value))
        
        # Apply resolution
        resolution = self.get_node_property('resolution', 8)
        max_digital_value = (2 ** resolution) - 1
        
        # Convert to digital value
        digital_value = int((constrained_value - min_value) / (max_value - min_value) * max_digital_value)
        
        # Update current value
        self.current_value = constrained_value
        
        # Send output command
        self._send_analog_output(digital_value)
        
        # Store value in flow context
        self.set_flow_variable(f'analog_out_{self.node_id}', constrained_value)
        
        return {
            'output': constrained_value,
            'digital_value': digital_value,
            'pin': self.get_node_property('outputPin'),
            'percentage': (constrained_value - min_value) / (max_value - min_value) * 100,
            'timestamp': timezone.now().isoformat()
        }
    
    def _send_analog_output(self, value: int) -> None:
        """
        Send analog output command.
        
        Args:
            value: Digital value to output
        """
        try:
            # Prepare output command
            command = {
                'type': 'analog_output',
                'node_id': self.node_id,
                'pin': self.get_node_property('outputPin'),
                'value': value,
                'timestamp': timezone.now().isoformat()
            }
            
            # Send to flow execution group
            if self.channel_layer:
                async_to_sync(self.channel_layer.group_send)(
                    f'flow_execution_{self.flow_context.get("execution_id")}',
                    {
                        'type': 'analog_output',
                        'message': command
                    }
                )
            
        except Exception as e:
            raise ExecutionError(f"Failed to send analog output: {str(e)}")

class DisplayProcessor(BaseProcessor):
    """
    Processor for display output nodes.
    
    Handles displaying data in various formats.
    Configuration:
    - displayType: 'text', 'number', 'chart', 'gauge' (default: 'text')
    - format: Display format string (optional)
    - precision: Number of decimal places for numbers
    - unit: Unit to display with the value
    """
    
    def __init__(self, node_config: Dict[str, Any], flow_context: Optional[Dict[str, Any]] = None):
        super().__init__(node_config, flow_context)
        self.channel_layer = get_channel_layer()
        self.display_history = []
    
    def validate_config(self) -> None:
        super().validate_config()
        
        display_type = self.get_node_property('displayType', 'text')
        if display_type not in ['text', 'number', 'chart', 'gauge']:
            raise ValidationError("Display type must be 'text', 'number', 'chart', or 'gauge'")
        
        precision = self.get_node_property('precision')
        if precision is not None and (not isinstance(precision, int) or precision < 0):
            raise ValidationError("Display precision must be a non-negative integer")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute display output.
        
        Args:
            input_data: Data to display
            
        Returns:
            Dict with display result
        """
        # Get input value
        value = input_data.get('output') or input_data.get('value')
        
        if value is None:
            display_text = "No data"
        else:
            display_text = self._format_display_value(value)
        
        # Add to display history
        display_entry = {
            'value': value,
            'formatted': display_text,
            'timestamp': timezone.now().isoformat()
        }
        
        self.display_history.append(display_entry)
        
        # Keep only last 100 entries
        if len(self.display_history) > 100:
            self.display_history.pop(0)
        
        # Send display update
        self._send_display_update(display_text, value)
        
        # Store in flow context
        self.set_flow_variable(f'display_{self.node_id}', display_text)
        
        return {
            'output': display_text,
            'raw_value': value,
            'display_type': self.get_node_property('displayType', 'text'),
            'timestamp': timezone.now().isoformat()
        }
    
    def _format_display_value(self, value: Any) -> str:
        """
        Format value for display.
        
        Args:
            value: Value to format
            
        Returns:
            Formatted string
        """
        display_type = self.get_node_property('displayType', 'text')
        format_string = self.get_node_property('format')
        precision = self.get_node_property('precision')
        unit = self.get_node_property('unit', '')
        
        if display_type == 'number' and isinstance(value, (int, float)):
            if precision is not None:
                formatted = f"{value:.{precision}f}"
            else:
                formatted = str(value)
            
            if unit:
                formatted += f" {unit}"
            
            return formatted
        
        elif format_string:
            try:
                return format_string.format(value=value)
            except:
                return str(value)
        
        else:
            return str(value)
    
    def _send_display_update(self, display_text: str, raw_value: Any) -> None:
        """
        Send display update to WebSocket.
        
        Args:
            display_text: Formatted display text
            raw_value: Raw value
        """
        try:
            # Prepare display update
            update = {
                'type': 'display_update',
                'node_id': self.node_id,
                'display_text': display_text,
                'raw_value': raw_value,
                'display_type': self.get_node_property('displayType', 'text'),
                'timestamp': timezone.now().isoformat()
            }
            
            # Send to flow execution group
            if self.channel_layer:
                async_to_sync(self.channel_layer.group_send)(
                    f'flow_execution_{self.flow_context.get("execution_id")}',
                    {
                        'type': 'display_update',
                        'message': update
                    }
                )
            
        except Exception as e:
            raise ExecutionError(f"Failed to send display update: {str(e)}")
    
    def get_display_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get display history.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of display history entries
        """
        return self.display_history[-limit:]
