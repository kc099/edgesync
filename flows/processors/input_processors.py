from typing import Dict, Any
from .base_processor import BaseProcessor, ValidationError

class ButtonProcessor(BaseProcessor):
    """
    Processor for button input nodes.
    
    Handles button press events and outputs a signal when pressed.
    Configuration:
    - label: Button display text
    - value: Value to output when pressed (default: True)
    """
    
    def validate_config(self) -> None:
        super().validate_config()
        # Button nodes don't require specific validation beyond base
        pass
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute button press.
        
        Args:
            input_data: Should contain 'pressed' key indicating button state
            
        Returns:
            Dict with button output value
        """
        # Check if button was pressed
        pressed = input_data.get('pressed', False)
        
        if pressed:
            # Get configured output value or default to True
            output_value = self.get_node_property('value', True)
            
            # Store button state in flow context for other nodes
            self.set_flow_variable(f'button_{self.node_id}', output_value)
            
            return {
                'output': output_value,
                'pressed': True,
                'timestamp': input_data.get('timestamp')
            }
        
        return {
            'output': None,
            'pressed': False
        }

class SliderProcessor(BaseProcessor):
    """
    Processor for slider input nodes.
    
    Handles slider value changes and outputs the current value.
    Configuration:
    - min: Minimum value (default: 0)
    - max: Maximum value (default: 100)
    - step: Step size (default: 1)
    - defaultValue: Initial value
    """
    
    def validate_config(self) -> None:
        super().validate_config()
        
        min_val = self.get_node_property('min', 0)
        max_val = self.get_node_property('max', 100)
        step = self.get_node_property('step', 1)
        
        if min_val >= max_val:
            raise ValidationError("Slider min value must be less than max value")
        
        if step <= 0:
            raise ValidationError("Slider step must be positive")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute slider value processing.
        
        Args:
            input_data: Should contain 'value' key with slider position
            
        Returns:
            Dict with processed slider value
        """
        # Get current slider value
        raw_value = input_data.get('value')
        
        if raw_value is None:
            # Use default value if no input provided
            raw_value = self.get_node_property('defaultValue', 0)
        
        # Validate and constrain value within bounds
        min_val = self.get_node_property('min', 0)
        max_val = self.get_node_property('max', 100)
        
        # Ensure value is within bounds
        constrained_value = max(min_val, min(max_val, float(raw_value)))
        
        # Store slider value in flow context
        self.set_flow_variable(f'slider_{self.node_id}', constrained_value)
        
        return {
            'output': constrained_value,
            'min': min_val,
            'max': max_val,
            'normalized': (constrained_value - min_val) / (max_val - min_val)
        }

class TextInputProcessor(BaseProcessor):
    """
    Processor for text input nodes.
    
    Handles text input and basic string processing.
    Configuration:
    - placeholder: Placeholder text
    - maxLength: Maximum text length
    - multiline: Whether to allow multiple lines
    """
    
    def validate_config(self) -> None:
        super().validate_config()
        
        max_length = self.get_node_property('maxLength')
        if max_length is not None and max_length <= 0:
            raise ValidationError("Text input maxLength must be positive")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute text input processing.
        
        Args:
            input_data: Should contain 'text' key with input text
            
        Returns:
            Dict with processed text output
        """
        # Get input text
        text = input_data.get('text', '')
        
        # Ensure text is string
        if not isinstance(text, str):
            text = str(text)
        
        # Apply length constraint if configured
        max_length = self.get_node_property('maxLength')
        if max_length is not None:
            text = text[:max_length]
        
        # Store text in flow context
        self.set_flow_variable(f'text_{self.node_id}', text)
        
        return {
            'output': text,
            'length': len(text),
            'isEmpty': len(text) == 0,
            'words': len(text.split()) if text.strip() else 0
        }

class NumberInputProcessor(BaseProcessor):
    """
    Processor for number input nodes.
    
    Handles numeric input with validation and formatting.
    Configuration:
    - min: Minimum allowed value
    - max: Maximum allowed value
    - step: Step size for increments
    - decimals: Number of decimal places
    - defaultValue: Default numeric value
    """
    
    def validate_config(self) -> None:
        super().validate_config()
        
        min_val = self.get_node_property('min')
        max_val = self.get_node_property('max')
        
        if min_val is not None and max_val is not None and min_val >= max_val:
            raise ValidationError("Number input min value must be less than max value")
        
        step = self.get_node_property('step')
        if step is not None and step <= 0:
            raise ValidationError("Number input step must be positive")
        
        decimals = self.get_node_property('decimals')
        if decimals is not None and decimals < 0:
            raise ValidationError("Number input decimals must be non-negative")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute number input processing.
        
        Args:
            input_data: Should contain 'value' key with numeric input
            
        Returns:
            Dict with processed numeric output
        """
        # Get input value
        raw_value = input_data.get('value')
        
        if raw_value is None:
            # Use default value if no input provided
            raw_value = self.get_node_property('defaultValue', 0)
        
        # Convert to number
        try:
            numeric_value = float(raw_value)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid numeric value: {raw_value}")
        
        # Apply bounds if configured
        min_val = self.get_node_property('min')
        max_val = self.get_node_property('max')
        
        if min_val is not None:
            numeric_value = max(min_val, numeric_value)
        
        if max_val is not None:
            numeric_value = min(max_val, numeric_value)
        
        # Apply decimal precision if configured
        decimals = self.get_node_property('decimals')
        if decimals is not None:
            numeric_value = round(numeric_value, decimals)
        
        # Store number in flow context
        self.set_flow_variable(f'number_{self.node_id}', numeric_value)
        
        return {
            'output': numeric_value,
            'isInteger': numeric_value == int(numeric_value),
            'isPositive': numeric_value > 0,
            'isNegative': numeric_value < 0,
            'abs': abs(numeric_value)
        }
