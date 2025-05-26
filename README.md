# ESP32 Sensor Dashboard with Django Channels

A real-time sensor data dashboard that receives data from ESP32 devices via WebSocket connections and displays it in a beautiful web interface.

## Features

- ✅ **WebSocket Server**: Django Channels-based WebSocket endpoint for ESP32 connections
- ✅ **Real-time Updates**: Live data streaming to web browsers
- ✅ **Data Persistence**: Automatic storage of sensor readings in SQLite database
- ✅ **REST API**: Historical data access via RESTful endpoints
- ✅ **Beautiful Dashboard**: Modern, responsive web interface with real-time charts
- ✅ **Multi-device Support**: Handle multiple ESP32 devices simultaneously
- ✅ **Filtering**: Filter data by device ID and sensor type
- ✅ **Admin Interface**: Django admin for data management

## Installation

1. **Clone the repository** (if applicable) or ensure you're in the project directory

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run database migrations**:
   ```bash
   python manage.py migrate
   ```

4. **Create a superuser** (optional, for admin access):
   ```bash
   python manage.py createsuperuser
   ```

5. **Start the ASGI server** (required for WebSocket functionality):
   
   **Option A - Use the startup script (recommended)**:
   ```bash
   python start_server.py
   ```
   
   **Option B - Manual Daphne command**:
   ```bash
   daphne -p 8000 edgesync.asgi:application
   ```
   
   **⚠️ Important**: The standard `python manage.py runserver` does NOT support WebSockets. You must use Daphne or another ASGI server.

6. **Optional: For production, set up Redis** (for multi-process deployments):
   - Install Redis and update `CHANNEL_LAYERS` in settings.py to use `channels_redis.core.RedisChannelLayer`
   - Current configuration uses in-memory channels (single-process only)

7. **Access the dashboard**:
   - Open your browser and go to `http://localhost:8000`
   - Admin interface: `http://localhost:8000/admin`

## ESP32 Integration

### WebSocket Endpoint
Your ESP32 devices should connect to: `ws://your-server:8000/ws/sensors/`

### Data Format
Send JSON data in the following format:
```json
{
    "device_id": "ESP32_001",
    "sensor_type": "temperature",
    "value": 23.5,
    "unit": "°C"
}
```

### Required Fields
- `device_id`: Unique identifier for your ESP32 device
- `sensor_type`: Type of sensor (e.g., "temperature", "humidity", "pressure")
- `value`: Numeric sensor reading
- `unit`: Unit of measurement (optional)

### ESP32 Example Code (Arduino IDE)

```cpp
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* websocket_server = "192.168.1.100";  // Your Django server IP
const int websocket_port = 8000;

WebSocketsClient webSocket;

void setup() {
    Serial.begin(115200);
    
    // Connect to WiFi
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(1000);
        Serial.println("Connecting to WiFi...");
    }
    Serial.println("WiFi connected!");
    
    // Initialize WebSocket connection
    webSocket.begin(websocket_server, websocket_port, "/ws/sensors/");
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
}

void loop() {
    webSocket.loop();
    
    // Send sensor data every 10 seconds
    static unsigned long lastSend = 0;
    if (millis() - lastSend > 10000) {
        sendSensorData();
        lastSend = millis();
    }
}

void sendSensorData() {
    // Create JSON payload
    StaticJsonDocument<200> doc;
    doc["device_id"] = "ESP32_001";
    doc["sensor_type"] = "temperature";
    doc["value"] = random(200, 300) / 10.0;  // Random temperature 20-30°C
    doc["unit"] = "°C";
    
    String payload;
    serializeJson(doc, payload);
    
    // Send via WebSocket
    webSocket.sendTXT(payload);
    Serial.println("Sent: " + payload);
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.println("WebSocket Disconnected");
            break;
        case WStype_CONNECTED:
            Serial.printf("WebSocket Connected to: %s\n", payload);
            break;
        case WStype_TEXT:
            Serial.printf("Received: %s\n", payload);
            break;
        default:
            break;
    }
}
```

### Required Arduino Libraries
- `WiFi` (built-in)
- `WebSocketsClient` by Markus Sattler
- `ArduinoJson` by Benoit Blanchon

## API Endpoints

### REST API
- `GET /api/data/` - List all sensor data with filtering
  - Query parameters: `device_id`, `sensor_type`, `ordering`
- `GET /api/summary/` - Get summary statistics
- `GET /api/latest/` - Get latest reading for each device/sensor combination

### WebSocket
- `ws://localhost:8000/ws/sensors/` - WebSocket endpoint for real-time data

## Dashboard Features

### Real-time Display
- Live sensor cards showing current values
- Real-time charts with historical data
- Connection status indicator
- Automatic reconnection on disconnect

### Filtering
- Filter by device ID
- Filter by sensor type
- Dynamic filter options based on available data

### Data Log
- Scrollable log of recent sensor readings
- Timestamps and device information
- Highlighting of new entries

## Project Structure

```
edgesync/
├── edgesync/
│   ├── settings.py          # Django settings with Channels config
│   ├── asgi.py             # ASGI configuration for WebSockets
│   └── urls.py             # Main URL configuration
├── sensors/
│   ├── models.py           # SensorData model
│   ├── consumers.py        # WebSocket consumer
│   ├── views.py            # REST API views
│   ├── serializers.py      # DRF serializers
│   ├── routing.py          # WebSocket routing
│   ├── admin.py            # Django admin configuration
│   └── templates/
│       └── sensors/
│           └── dashboard.html  # Main dashboard template
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Troubleshooting

### WebSocket Connection Issues
1. **Use Daphne, not Django dev server**: `python manage.py runserver` does NOT support WebSockets
2. **Correct command**: Use `daphne -p 8000 edgesync.asgi:application`
3. **Check server logs**: Look for import errors or Django configuration issues
4. **Verify WebSocket URL**: Should be `ws://localhost:8000/ws/sensors/`
5. **For production**: Set up Redis and update CHANNEL_LAYERS configuration

### ESP32 Connection Problems
1. Verify WiFi credentials
2. Check server IP address
3. Ensure WebSocket libraries are installed
4. Monitor Serial output for error messages

### Database Issues
1. Run migrations: `python manage.py migrate`
2. Check database permissions
3. Verify SQLite file location

## Development

### Adding New Sensor Types
1. No code changes needed - the system automatically handles new sensor types
2. Icons for new sensor types can be added in the `getSensorIcon()` function in the dashboard template

### Customizing the Dashboard
- Edit `sensors/templates/sensors/dashboard.html`
- Modify CSS styles in the `<style>` section
- Add new JavaScript functionality in the `<script>` section

### Extending the API
- Add new views in `sensors/views.py`
- Create new URL patterns in `sensors/urls.py`
- Add new serializers in `sensors/serializers.py`

## License

This project is open source and available under the MIT License. 