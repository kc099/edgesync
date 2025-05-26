import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import SensorData

logger = logging.getLogger(__name__)

class SensorDataConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for handling ESP32 sensor data and web client connections"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.room_group_name = 'sensor_data'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connection established: {self.channel_name}")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket connection closed: {self.channel_name}, code: {close_code}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            logger.info(f"Received data: {data}")
            
            # Check if this is sensor data from ESP32
            if self.is_esp32_data(data):
                # Save to database
                sensor_data = await self.save_sensor_data(data)
                
                # Prepare data for broadcasting
                broadcast_data = {
                    'type': 'sensor_data',
                    'device_id': sensor_data.device_id,
                    'sensor_type': sensor_data.sensor_type,
                    'value': sensor_data.value,
                    'unit': sensor_data.unit,
                    'timestamp': sensor_data.timestamp.isoformat(),
                    'id': sensor_data.id
                }
                
                # Broadcast to all connected clients
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'sensor_data_message',
                        'data': broadcast_data
                    }
                )
                
                # Send confirmation back to ESP32
                await self.send(text_data=json.dumps({
                    'status': 'success',
                    'message': 'Data received and saved',
                    'id': sensor_data.id
                }))
            else:
                # Handle other types of messages (e.g., from web clients)
                logger.info(f"Non-sensor data received: {data}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {text_data}")
            await self.send(text_data=json.dumps({
                'status': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.send(text_data=json.dumps({
                'status': 'error',
                'message': str(e)
            }))
    
    async def sensor_data_message(self, event):
        """Handle sensor data broadcast to all clients"""
        data = event['data']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps(data))
    
    def is_esp32_data(self, data):
        """Check if the received data is from an ESP32 device"""
        required_fields = ['device_id', 'sensor_type', 'value']
        return all(field in data for field in required_fields)
    
    @database_sync_to_async
    def save_sensor_data(self, data):
        """Save sensor data to database"""
        return SensorData.create_from_esp32_data(data) 