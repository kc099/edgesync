/*
 * ESP32 Simple WebSocket Client (No Encryption)
 * Use this for initial testing before implementing encryption
 * 
 * Required Libraries:
 * - WiFi (built-in)
 * - WebSocketsClient by Markus Sattler
 * - ArduinoJson by Benoit Blanchon
 */

#include <WiFi.h>
#include <WebsocketsClient.h>
#include <ArduinoJson.h>

// WiFi Configuration
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// WebSocket Configuration
const char* websocket_host = "192.168.1.100"; // Replace with your server IP
const int websocket_port = 8000;
const char* websocket_path = "/ws/sensors/";
const char* device_token = "1234567890abcdef"; // Your device token

// WebSocket Client
WebSocketsClient webSocket;
String deviceUuid = "";
bool deviceReady = false;

// Timing
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 2000; // 2 seconds

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n🚀 ESP32 Simple WebSocket Client Starting...");
  
  // Connect to WiFi
  connectToWiFi();
  
  // Initialize WebSocket connection
  initializeWebSocket();
}

void loop() {
  webSocket.loop();
  
  // Send sensor data at regular intervals
  if (millis() - lastSensorRead >= SENSOR_INTERVAL && deviceReady) {
    sendSensorData();
    lastSensorRead = millis();
  }
  
  delay(10);
}

void connectToWiFi() {
  Serial.print("📶 Connecting to WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n✅ WiFi connected!");
  Serial.print("📍 IP address: ");
  Serial.println(WiFi.localIP());
}

void initializeWebSocket() {
  // Construct WebSocket URL with token
  String url = String(websocket_path) + "?token=" + String(device_token);
  
  Serial.println("🔌 Connecting to WebSocket server...");
  Serial.printf("📡 Server: %s:%d%s\n", websocket_host, websocket_port, url.c_str());
  
  webSocket.begin(websocket_host, websocket_port, url);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  
  Serial.println("⏳ Waiting for connection...");
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("❌ WebSocket Disconnected");
      deviceReady = false;
      break;
      
    case WStype_CONNECTED:
      Serial.printf("✅ WebSocket Connected to: %s\n", payload);
      Serial.println("⏳ Waiting for device_info message...");
      break;
      
    case WStype_TEXT:
      handleWebSocketMessage((char*)payload);
      break;
      
    case WStype_ERROR:
      Serial.printf("❌ WebSocket Error: %s\n", payload);
      break;
      
    default:
      break;
  }
}

void handleWebSocketMessage(const char* message) {
  Serial.printf("📨 Received: %s\n", message);
  
  // Parse JSON message
  DynamicJsonDocument doc(1024);
  DeserializationError error = deserializeJson(doc, message);
  
  if (error) {
    Serial.printf("❌ JSON parsing failed: %s\n", error.c_str());
    return;
  }
  
  // Handle device_info message
  if (doc["type"] == "device_info") {
    deviceUuid = doc["device_uuid"].as<String>();
    Serial.printf("📱 Received device UUID: %s\n", deviceUuid.c_str());
    
    deviceReady = true;
    Serial.println("✅ Device ready to send sensor data");
  }
}

void sendSensorData() {
  if (!deviceReady || deviceUuid.isEmpty()) {
    return;
  }
  
  // Create sensor readings JSON
  DynamicJsonDocument doc(1024);
  doc["device_id"] = deviceUuid;
  
  JsonArray readings = doc.createNestedArray("readings");
  
  // Temperature reading
  JsonObject tempReading = readings.createNestedObject();
  tempReading["sensor_type"] = "temperature";
  tempReading["value"] = random(2000, 3000) / 100.0; // 20.0-30.0°C
  tempReading["unit"] = "C";
  
  // Humidity reading
  JsonObject humReading = readings.createNestedObject();
  humReading["sensor_type"] = "humidity";
  humReading["value"] = random(4000, 6500) / 100.0; // 40.0-65.0%
  humReading["unit"] = "%";
  
  // Send the payload
  String payload;
  serializeJson(doc, payload);
  
  webSocket.sendTXT(payload);
  Serial.printf("📤 Sent payload with %d readings\n", readings.size());
}
