from typing import Dict, Any, Optional
from django.utils import timezone
from .base_processor import BaseProcessor, ValidationError, ExecutionError
from sensors.models import Device, SensorData
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json

class DeviceProcessor(BaseProcessor):
    """
    Processor for device nodes that interact with IoT devices.
    
    Handles reading sensor data from devices and sending control commands.
    Configuration:
    - deviceUuid: UUID of the device to interact with
    - variable: Device variable to read/write
    - mode: 'read' or 'write' mode
    - dataType: Expected data type ('number', 'string', 'boolean')
    """
    
    def __init__(self, node_config: Dict[str, Any], flow_context: Optional[Dict[str, Any]] = None):
        super().__init__(node_config, flow_context)
        self.device = None
        self.channel_layer = get_channel_layer()
    
    def validate_config(self) -> None:
        super().validate_config()
        
        device_uuid = self.get_node_property('deviceUuid')
        if not device_uuid:
            raise ValidationError("Device UUID is required for device nodes")
        
        variable = self.get_node_property('variable')
        if not variable:
            raise ValidationError("Device variable is required for device nodes")
        
        mode = self.get_node_property('mode', 'read')
        if mode not in ['read', 'write']:
            raise ValidationError("Device mode must be 'read' or 'write'")
        
        # Load and validate device
        try:
            self.device = Device.objects.get(uuid=device_uuid)
        except Device.DoesNotExist:
            raise ValidationError(f"Device with UUID {device_uuid} not found")
        
        # Check device status
        if not self.device.is_active:
            raise ValidationError(f"Device {self.device.name} is not active")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute device interaction.
        
        Args:
            input_data: Input data containing device commands or trigger
            
        Returns:
            Dict with device data or command result
        """
        mode = self.get_node_property('mode', 'read')
        variable = self.get_node_property('variable')
        
        if mode == 'read':
            return self._read_device_data(variable)
        elif mode == 'write':
            return self._write_device_data(variable, input_data)
        else:
            raise ExecutionError(f"Unknown device mode: {mode}")
    
    def _read_device_data(self, variable: str) -> Dict[str, Any]:
        """
        Read data from device variable.
        
        Args:
            variable: Variable name to read
            
        Returns:
            Dict with device data
        """
        try:
            # Get latest sensor data for this device and variable
            sensor_data = SensorData.objects.filter(
                device_id=self.device.device_id or str(self.device.uuid),
                sensor_type=variable
            ).first()
            
            if not sensor_data:
                # No data available, return None
                return {
                    'output': None,
                    'device': self.device.name,
                    'variable': variable,
                    'timestamp': None,
                    'status': 'no_data'
                }
            
            # Convert data based on expected type
            data_type = self.get_node_property('dataType', 'number')
            processed_value = self._convert_data_type(sensor_data.value, data_type)
            
            # Store device data in flow context
            self.set_flow_variable(f'device_{self.node_id}', processed_value)
            
            return {
                'output': processed_value,
                'device': self.device.name,
                'variable': variable,
                'timestamp': sensor_data.timestamp.isoformat(),
                'unit': sensor_data.unit,
                'raw_value': sensor_data.value,
                'status': 'success'
            }
            
        except Exception as e:
            raise ExecutionError(f"Failed to read device data: {str(e)}")
    
    def _write_device_data(self, variable: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Write data to device variable.
        
        Args:
            variable: Variable name to write
            input_data: Data to write to device
            
        Returns:
            Dict with write operation result
        """
        try:
            # Get value to write from input data
            value = input_data.get('output') or input_data.get('value')
            
            if value is None:
                raise ExecutionError("No value provided for device write operation")
            
            # Convert data based on expected type
            data_type = self.get_node_property('dataType', 'number')
            processed_value = self._convert_data_type(value, data_type)
            
            # Send command to device via WebSocket
            self._send_device_command(variable, processed_value)
            
            # Store the sent value in flow context
            self.set_flow_variable(f'device_{self.node_id}_sent', processed_value)
            
            return {
                'output': processed_value,
                'device': self.device.name,
                'variable': variable,
                'timestamp': timezone.now().isoformat(),
                'status': 'sent'
            }
            
        except Exception as e:
            raise ExecutionError(f"Failed to write device data: {str(e)}")
    
    def _convert_data_type(self, value: Any, data_type: str) -> Any:
        """
        Convert value to specified data type.
        
        Args:
            value: Value to convert
            data_type: Target data type
            
        Returns:
            Converted value
        """
        try:
            if data_type == 'number':
                return float(value)
            elif data_type == 'boolean':
                if isinstance(value, str):
                    return value.lower() in ['true', '1', 'on', 'yes']
                return bool(value)
            elif data_type == 'string':
                return str(value)
            else:
                return value
        except (ValueError, TypeError):
            raise ExecutionError(f"Cannot convert {value} to {data_type}")
    
    def _send_device_command(self, variable: str, value: Any) -> None:
        """
        Send command to device via WebSocket.
        
        Args:
            variable: Variable name
            value: Value to send
        """
        try:
            # Prepare command message
            command = {
                'type': 'device_command',
                'device_uuid': str(self.device.uuid),
                'variable': variable,
                'value': value,
                'timestamp': timezone.now().isoformat()
            }
            
            # Send to device WebSocket group
            device_group = f'device_{self.device.uuid}'
            
            if self.channel_layer:
                async_to_sync(self.channel_layer.group_send)(
                    device_group,
                    {
                        'type': 'device_command',
                        'message': command
                    }
                )
            
        except Exception as e:
            raise ExecutionError(f"Failed to send device command: {str(e)}")
    
    def get_device_status(self) -> Dict[str, Any]:
        """
        Get current device status information.
        
        Returns:
            Dict with device status
        """
        if not self.device:
            return {'status': 'unknown', 'message': 'Device not loaded'}
        
        return {
            'status': self.device.status,
            'is_active': self.device.is_active,
            'last_seen': self.device.last_seen.isoformat() if self.device.last_seen else None,
            'name': self.device.name,
            'uuid': str(self.device.uuid)
        }
    
    def get_latest_sensor_data(self, variable: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent sensor data for a variable.
        
        Args:
            variable: Variable name
            limit: Maximum number of records to return
            
        Returns:
            List of sensor data records
        """
        if not self.device:
            return []
        
        sensor_data = SensorData.objects.filter(
            device_id=self.device.device_id or str(self.device.uuid),
            sensor_type=variable
        ).order_by('-timestamp')[:limit]
        
        return [
            {
                'value': data.value,
                'unit': data.unit,
                'timestamp': data.timestamp.isoformat(),
                'raw_data': data.raw_data
            }
            for data in sensor_data
        ]
