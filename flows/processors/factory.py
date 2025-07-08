from typing import Dict, Any, Optional, Type, List
from .base_processor import BaseProcessor, ValidationError
from .input_processors import (
    ButtonProcessor,
    SliderProcessor,
    TextInputProcessor,
    NumberInputProcessor
)
from .output_processors import (
    DigitalOutputProcessor,
    AnalogOutputProcessor,
    DisplayProcessor
)
from .function_processors import (
    MovingAverageProcessor,
    MinMaxProcessor,
    CommentProcessor,
    DebugProcessor,
    CustomFunctionProcessor
)
from .device_processors import DeviceProcessor

class ProcessorFactory:
    """
    Factory class for creating node processors based on node type.
    
    Maps node types from the React Flow editor to their corresponding
    processor classes.
    """
    
    # Mapping of node types to processor classes
    PROCESSOR_MAP = {
        # Input nodes
        'button': ButtonProcessor,
        'slider': SliderProcessor,
        'text-input': TextInputProcessor,
        'number-input': NumberInputProcessor,
        
        # Output nodes
        'digital-output': DigitalOutputProcessor,
        'analog-output': AnalogOutputProcessor,
        'display': DisplayProcessor,
        
        # Function nodes
        'moving-average': MovingAverageProcessor,
        'min-max': MinMaxProcessor,
        'comment': CommentProcessor,
        'debug': DebugProcessor,
        'custom-function': CustomFunctionProcessor,
        
        # Device nodes
        'device': DeviceProcessor,
    }
    
    @classmethod
    def create_processor(
        cls, 
        node_config: Dict[str, Any], 
        flow_context: Optional[Dict[str, Any]] = None
    ) -> BaseProcessor:
        """
        Create a processor instance for a given node configuration.
        
        Args:
            node_config: Node configuration from React Flow
            flow_context: Optional flow-level context
            
        Returns:
            Processor instance
            
        Raises:
            ValidationError: If node type is unknown or invalid
        """
        node_type = node_config.get('type')
        node_data = node_config.get('data', {})
        
        # Check for nodeType in data (React Flow specific)
        if not node_type and 'nodeType' in node_data:
            node_type = node_data['nodeType']
        
        if not node_type:
            raise ValidationError("Node type is required")
        
        # Get processor class
        processor_class = cls.PROCESSOR_MAP.get(node_type)
        
        if not processor_class:
            raise ValidationError(f"Unknown node type: {node_type}")
        
        # Create and return processor instance
        return processor_class(node_config, flow_context)
    
    @classmethod
    def get_supported_node_types(cls) -> List[str]:
        """
        Get list of supported node types.
        
        Returns:
            List of supported node type strings
        """
        return list(cls.PROCESSOR_MAP.keys())
    
    @classmethod
    def register_processor(cls, node_type: str, processor_class: Type[BaseProcessor]) -> None:
        """
        Register a new processor class for a node type.
        
        Args:
            node_type: Node type string
            processor_class: Processor class
        """
        cls.PROCESSOR_MAP[node_type] = processor_class
    
    @classmethod
    def unregister_processor(cls, node_type: str) -> None:
        """
        Unregister a processor class for a node type.
        
        Args:
            node_type: Node type string
        """
        cls.PROCESSOR_MAP.pop(node_type, None)
    
    @classmethod
    def is_supported_node_type(cls, node_type: str) -> bool:
        """
        Check if a node type is supported.
        
        Args:
            node_type: Node type string
            
        Returns:
            True if supported, False otherwise
        """
        return node_type in cls.PROCESSOR_MAP
    
    @classmethod
    def get_processor_class(cls, node_type: str) -> Optional[Type[BaseProcessor]]:
        """
        Get processor class for a node type.
        
        Args:
            node_type: Node type string
            
        Returns:
            Processor class or None if not found
        """
        return cls.PROCESSOR_MAP.get(node_type)
