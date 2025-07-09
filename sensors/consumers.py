import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import SensorData, Device, TrackedVariable, WidgetSample
import urllib.parse
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.utils import timezone

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

        # If this socket belongs to a device, send its canonical UUID so the
        # firmware/client does not need to hard-code or separately fetch it.
        if self.is_device and self.device:
            try:
                await self.send(text_data=json.dumps({
                    "type": "device_info",
                    "device_uuid": str(self.device.uuid)
                }))
            except Exception as e:
                logger.debug(f"Failed to send device_info payload: {e}")

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
            
            # Support two payload formats:
            # 1) Single reading: {device_id, sensor_type, value, unit}
            # 2) Bulk readings:  {device_id, readings: [{sensor_type, value, unit?}, ...]}
            if "readings" in data:
                # ---------------------------- BULK READINGS -----------------------------
                # Normalise device_id to canonical UUID when authenticated device
                if self.device:
                    data["device_id"] = str(self.device.uuid)
                device_id = data.get("device_id")

                readings = data["readings"]
                # Allow {"temperature": 25.4, "humidity": 60} style objects as shorthand
                if isinstance(readings, dict):
                    readings = [
                        {"sensor_type": k, "value": v} for k, v in readings.items()
                    ]

                saved_count = 0
                for reading in readings:
                    reading_payload = {
                        "device_id": device_id,
                        "sensor_type": reading.get("sensor_type") or reading.get("type"),
                        "value": reading.get("value"),
                        "unit": reading.get("unit", "")
                    }
                    if not self.is_esp32_data(reading_payload):
                        logger.debug(f"Skipping invalid reading fragment: {reading}")
                        continue

                    sensor_data = await self.save_sensor_data(reading_payload)
                    saved_count += 1

                    broadcast_data = {
                        'type': 'sensor_data',
                        'device_id': device_id,
                        'sensor_type': sensor_data.sensor_type,
                        'value': sensor_data.value,
                        'unit': sensor_data.unit,
                        'timestamp': sensor_data.timestamp.isoformat(),
                        'id': sensor_data.id
                    }

                    # Broadcast each reading independently so existing frontend code keeps working
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'sensor_data_message',
                            'data': broadcast_data
                        }
                    )

                    # ---------------- Persist / broadcast for widgets ----------------
                    await self._handle_widget_tracking(
                        device_id=device_id,
                        sensor_type=sensor_data.sensor_type,
                        value=sensor_data.value,
                        unit=sensor_data.unit,
                        timestamp=sensor_data.timestamp,
                    )

                await self.send(text_data=json.dumps({
                    'status': 'success',
                    'message': f'{saved_count} readings received and saved'
                }))

            elif self.is_esp32_data(data):
                # ---------------------------- SINGLE READING -----------------------------
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

                await self._handle_widget_tracking(
                    device_id=broadcast_data['device_id'],
                    sensor_type=broadcast_data['sensor_type'],
                    value=broadcast_data['value'],
                    unit=broadcast_data['unit'],
                    timestamp=timezone.now(),
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

    # ---------------------------------------------------------------------
    # Widget tracking helpers
    # ---------------------------------------------------------------------

    async def _handle_widget_tracking(self, *, device_id: str, sensor_type: str, value: float, unit: str, timestamp):
        """Persist sample & broadcast to any widgets that track this variable."""
        tracked_vars = await database_sync_to_async(list)(
            TrackedVariable.objects.filter(device_id=device_id, sensor_type=sensor_type)
        )
        if not tracked_vars:
            return

        for tv in tracked_vars:
            # Save sample
            await database_sync_to_async(WidgetSample.objects.create)(
                widget=tv,
                timestamp=timestamp,
                value=value,
                unit=unit,
            )

            # Trim to max_samples
            await database_sync_to_async(self._trim_samples)(tv)

            # Broadcast to widget group
            await self.channel_layer.group_send(
                f'widget_{tv.widget_id}',
                {
                    'type': 'widget_update',
                    'payload': {
                        'timestamp': timestamp.isoformat(),
                        'value': value,
                        'unit': unit,
                    }
                }
            )

    def _trim_samples(self, tv):
        qs = WidgetSample.objects.filter(widget=tv).order_by('-timestamp')
        excess = qs[tv.max_samples:]
        if excess:
            WidgetSample.objects.filter(id__in=[s.id for s in excess]).delete()

# ---------------------------------------------------------------------------
# Consumer for dashboard widgets (read-only, just receives updates)
# ---------------------------------------------------------------------------


class WidgetDataConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info(f"WidgetDataConsumer connect attempt: path={self.scope.get('path')} query={self.scope.get('query_string')} user={self.scope.get('user')}")
        
        # --- Authentication (same pattern as SensorDataConsumer) ---------
        # Check for JWT token in query params
        query_params = urllib.parse.parse_qs(self.scope.get("query_string", b"").decode())
        token_param = query_params.get("token", [None])[0]

        if token_param:
            # Validate JWT token and set user in scope
            try:
                UntypedToken(token_param)  # validates signature & expiry
                from rest_framework_simplejwt.authentication import JWTAuthentication
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(token_param)
                user = await database_sync_to_async(jwt_auth.get_user)(validated_token)
                self.scope["user"] = user
            except (InvalidToken, TokenError) as e:
                logger.warning("Invalid JWT token provided for widget connection – rejecting")
                await self.close(code=4001)
                return

        # Check if user is authenticated
        user = self.scope.get("user")
        if not (user and user.is_authenticated):
            logger.warning("Unauthenticated widget websocket connection attempted – rejecting")
            await self.close(code=4003)
            return
        # -----------------------------------------------------------------
        
        self.widget_id = self.scope['url_route']['kwargs']['widget_id']
        self.group_name = f'widget_{self.widget_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        logger.info(f"WidgetDataConsumer connection established for widget: {self.widget_id}, user: {user.username if user else 'Anonymous'}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WidgetDataConsumer disconnected: widget={self.widget_id}, code={close_code}")

    async def widget_update(self, event):
        await self.send(text_data=json.dumps(event['payload'])) 