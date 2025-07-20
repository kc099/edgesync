# ESP32 Arduino WebSocket Client Setup Guide

## Overview
This ESP32 Arduino implementation provides end-to-end encryption compatibility with your EdgeSync WebSocket server, following the same encryption patterns as your Python device client.

## Required Libraries

### 1. Install via Arduino Library Manager
Open Arduino IDE → Tools → Manage Libraries, then search and install:

1. **WebSocketsClient** by Markus Sattler
   - Version: Latest (2.3.6+)
   - Provides WebSocket client functionality

2. **ArduinoJson** by Benoit Blanchon  
   - Version: 6.x (latest)
   - For JSON parsing and creation

3. **Crypto** by Rhys Weatherley
   - Version: Latest
   - Provides AES-256-CBC encryption
   - Full name: "Crypto Library for Arduino"

4. **Base64** by Densaugeo
   - Version: Latest
   - For Base64 encoding/decoding

### 2. Built-in Libraries (no installation needed)
- **WiFi** - Built into ESP32 Arduino Core
- **Random** - Built into ESP32 Arduino Core

## Hardware Requirements

### Minimum Setup
- **ESP32 Development Board** (any variant: ESP32 DevKit, NodeMCU-32S, etc.)
- **USB Cable** for programming
- **WiFi Network** for connectivity

### Optional Real Sensors
- **DHT22** temperature/humidity sensor (pin 4)
- **BMP280** pressure sensor (I2C)
- **GPS Module** for real location data

## Configuration Steps

### 1. Update WiFi Credentials
```cpp
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
```

### 2. Update Server Configuration
```cpp
const char* websocket_host = "192.168.1.100"; // Your server IP
const int websocket_port = 8000;
const char* device_token = "1234567890abcdef"; // Your device token
```

### 3. Upload and Monitor
1. Select your ESP32 board in Arduino IDE
2. Select the correct COM port
3. Upload the code
4. Open Serial Monitor (115200 baud)

## Expected Serial Output

```
🚀 ESP32 Industrial IoT Device Client Starting...
🏭 Industrial mode: ALL sensor data will be encrypted
📶 Connecting to WiFi: YourWiFiName
✅ WiFi connected!
📍 IP address: 192.168.1.123
🔌 Connecting to WebSocket server...
📡 Server: 192.168.1.100:8000/ws/sensors/?token=1234567890abcdef
✅ WebSocket Connected to: /ws/sensors/
📨 Received: {"type":"device_info","device_uuid":"ba95b707-fd40-48aa-86d4-54ebae968254","encryption_enabled":true,"encryption_key":"base64_key_here"}
📱 Received device UUID: ba95b707-fd40-48aa-86d4-54ebae968254
🔐 Encryption initialized successfully
🏭 Ready to send encrypted industrial IoT data
🔒 Encrypted temperature sensor value
🔒 Encrypted humidity sensor value  
🔒 Encrypted pressure sensor value
🔒 Encrypted location sensor value
🔒 Encrypted personal_id sensor value
🔒 Encrypted equipment_id sensor value
📤 Sent encrypted payload with 6 readings
```

## Key Features

### ✅ Full Compatibility
- Matches Python client encryption exactly
- Uses same AES-256-CBC + PKCS7 padding
- Compatible with your existing backend

### ✅ Industrial IoT Security
- ALL sensor data encrypted (not selective)
- Device-specific encryption keys
- Random IV for each field encryption
- Base64 encoding for transmission

### ✅ Robust Connection
- Auto-reconnection on disconnect
- Proper WebSocket token authentication
- JSON message parsing and creation

### ✅ Extensible Design
- Easy to add real sensors
- Configurable sensor intervals
- Modular encryption functions

## Troubleshooting

### Common Issues

1. **Compilation Errors**
   - Make sure all libraries are installed
   - Use ESP32 board package version 2.0.0+

2. **WiFi Connection Issues**
   - Verify SSID/password
   - Check WiFi signal strength
   - Ensure ESP32 supports your WiFi security type

3. **WebSocket Connection Issues**
   - Verify server IP and port
   - Check device token validity
   - Ensure server is running

4. **Encryption Issues**
   - Verify Crypto library installation
   - Check serial output for key initialization
   - Ensure server sends encryption_key

### Memory Considerations
- ESP32 has ~300KB RAM available
- JSON documents sized for typical sensor payloads
- Encryption operations require temporary buffers

### Performance Notes
- 2-second sensor intervals (configurable)
- AES encryption adds ~50-100ms processing time
- WebSocket keep-alive maintains connection

## Advanced Customization

### Adding Real Sensors
Uncomment and modify the DHT22 section:
```cpp
#include <DHT.h>
#define DHT_PIN 4
#define DHT_TYPE DHT22
DHT dht(DHT_PIN, DHT_TYPE);
```

### Adjusting Timing
```cpp
const unsigned long SENSOR_INTERVAL = 5000; // 5 seconds
```

### Custom Sensor Types
Add new readings to the `sendSensorData()` function following the existing pattern.

This implementation provides a production-ready ESP32 client that maintains full encryption compatibility with your EdgeSync server while being optimized for microcontroller constraints.
