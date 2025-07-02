import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import SensorData, Device
import urllib.parse
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger(__name__)

class SensorDataConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for handling ESP32 sensor data and web client connections"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.room_group_name = 'sensor_data'
        
        # --- Authentication -------------------------------------------------
        # We support two authentication mechanisms:
        # 1. Logged-in dashboard/web users via Django sessions (handled by
        #    AuthMiddlewareStack – user will be in scope["user"].)
        # 2. Device clients authenticating via their unique device token that is
        #    passed as a query-string parameter, e.g. ws://host/ws/sensors/?token=<TOKEN>
        # -------------------------------------------------------------------

        # Check for device token in the query params
        query_params = urllib.parse.parse_qs(self.scope.get("query_string", b"").decode())
        token_param = query_params.get("token", [None])[0]

        self.device = None
        self.is_device = False  # flag to indicate this socket belongs to a device

        # If a token was supplied, try to authenticate device
        if token_param:
            # -------------------------------------------------------------------
            # 1) Attempt device-token authentication. This may raise various DB-
            #    related exceptions (e.g. when the provided token is much longer
            #    than the max_length of the field in some backends). We catch a
            #    broad Exception here to gracefully fall back to JWT handling.
            # -------------------------------------------------------------------
            try:
                self.device = await database_sync_to_async(Device.objects.get)(token=token_param)
                self.is_device = True
            except Device.DoesNotExist:
                pass  # Will attempt JWT handling below
            except Exception as e:  # e.g. DataError, ValueError, etc.
                logger.debug(f"Token did not match a device record – treating as JWT. Details: {e}")

            # If not resolved as device, interpret as (potential) JWT for a user
            if not self.is_device:
                try:
                    UntypedToken(token_param)  # validates signature & expiry
                    from rest_framework_simplejwt.authentication import JWTAuthentication
                    jwt_auth = JWTAuthentication()
                    validated_token = jwt_auth.get_validated_token(token_param)
                    user = await database_sync_to_async(jwt_auth.get_user)(validated_token)
                    self.scope["user"] = user
                except (InvalidToken, TokenError) as e:
                    logger.warning("Invalid auth token provided – connection rejected")
                    await self.close(code=4001)
                    return

        # If no valid device token, fall back to user authentication
        if not self.is_device:
            user = self.scope.get("user")
            if not (user and user.is_authenticated):
                logger.warning("Unauthenticated websocket connection attempted – rejecting")
                await self.close(code=4003)  # 4003 -> policy violation / auth required
                return

        # At this point authentication succeeded – join the broadcast group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        logger.info(
            f"WebSocket connection established: {self.channel_name} |"
            f" type={'device' if self.is_device else 'viewer'}"
        )
    
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
        # Only allow sensor-device connections (authenticated via token) to send
        # data. Viewer sockets can ignore/are not permitted to push data.
        if not self.is_device:
            logger.debug("Ignoring data received from non-device client")
            return
        try:
            data = json.loads(text_data)
            logger.info(f"Received data: {data}")
            
            # Check if this is sensor data from ESP32
            if self.is_esp32_data(data):
                # Override device_id with canonical UUID if authenticated device
                if self.device:
                    data["device_id"] = str(self.device.uuid)

                # Save to database
                sensor_data = await self.save_sensor_data(data)
                
                # Prepare data for broadcasting
                broadcast_data = {
                    'type': 'sensor_data',
                    'device_id': str(self.device.uuid) if self.device else sensor_data.device_id,
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
                logger.info(f"Non-sensor data received from device: {data}")
                
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