/*
 * ESP32 Industrial IoT Device Client with End-to-End Encryption
 * Compatible with EdgeSync WebSocket backend encryption system
 * 
 * Required Libraries (install via Arduino Library Manager):
 * - WiFi (built-in)
 * - WebSocketsClient by Markus Sattler
 * - ArduinoJson by Benoit Blanchon
 * - Crypto by Rhys Weatherley (for AES encryption)
 * - Base64 by Densaugeo
 * 
 * Hardware: ESP32 DevKit, DHT22 sensor (optional for real sensor data)
 */

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <Crypto.h>
#include <AES.h>
#include <CBC.h>
#include <RNG.h>
#include <base64.hpp>
#include <string.h>

// WiFi Configuration
const char* ssid = "Kugelblitz";
const char* password = "xxx";

// WebSocket Configuration
const char* websocket_host = "192.168.0.101"; // Replace with your server IP
const int websocket_port = 8000;
const char* websocket_path = "/ws/sensors/";
const char* device_token = "XWDWdQkDdmExLbBDKPAQu7dULLPp1dEYaj9l2FKHq9A"; // Your device token

// Encryption Configuration
CBC<AES256> aes256cbc;
byte deviceKey[32]; // 256-bit key
bool encryptionEnabled = false;
String deviceUuid = "";

// WebSocket Client
WebSocketsClient webSocket;

// Timing
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 2000; // 2 seconds

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n🚀 ESP32 Industrial IoT Device Client Starting...");
  Serial.println("🏭 Industrial mode: ALL sensor data will be encrypted");
  
  // Initialize random number generator for encryption
  RNG.begin("ESP32 Industrial IoT Device", 950);
  
  // Connect to WiFi
  connectToWiFi();
  
  // Initialize WebSocket connection
  initializeWebSocket();
}

void loop() {
  webSocket.loop();
  
  // Send sensor data at regular intervals
  if (millis() - lastSensorRead >= SENSOR_INTERVAL && encryptionEnabled) {
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
      encryptionEnabled = false;
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
    
    // Initialize encryption if provided
    if (doc["encryption_enabled"] == true && doc.containsKey("encryption_key")) {
      String keyBase64 = doc["encryption_key"];
      if (initializeEncryption(keyBase64)) {
        encryptionEnabled = true;
        Serial.println("🔐 Encryption initialized successfully");
        Serial.println("🏭 Ready to send encrypted industrial IoT data");
      } else {
        Serial.println("❌ Failed to initialize encryption");
      }
    } else {
      Serial.println("⚠️  WARNING: Encryption not enabled!");
      Serial.println("⚠️  Industrial IoT requires end-to-end encryption!");
    }
  }
}

bool initializeEncryption(const String& keyBase64) {
  // Decode base64 key
  int keyLength = decode_base64_length((uint8_t*)keyBase64.c_str(),
                      keyBase64.length());
  
  if (keyLength != 32) {
    Serial.printf("❌ Invalid key length: %d (expected 32)\n", keyLength);
    return false;
  }
  
  decode_base64((uint8_t*)keyBase64.c_str(),
                keyBase64.length(),
                deviceKey);
  
  Serial.printf("✅ Encryption key initialized (%d bytes)\n", keyLength);
  return true;
}

void sendSensorData() {
  if (!encryptionEnabled || deviceUuid.isEmpty()) {
    return;
  }
  
  // Create sensor readings JSON
  DynamicJsonDocument doc(2048);
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
  
  // Pressure reading
  JsonObject pressReading = readings.createNestedObject();
  pressReading["sensor_type"] = "pressure";
  pressReading["value"] = random(101000, 102500) / 100.0; // 1010.0-1025.0 hPa
  pressReading["unit"] = "hPa";
  
  // Location reading (GPS coordinates)
  JsonObject locReading = readings.createNestedObject();
  locReading["sensor_type"] = "location";
  locReading["value"] = "40." + String(random(100000, 999999)) + ",-73." + String(random(100000, 999999));
  locReading["unit"] = "lat,lng";
  
  // Personal ID reading
  JsonObject idReading = readings.createNestedObject();
  idReading["sensor_type"] = "personal_id";
  idReading["value"] = "USER_" + String(random(1000, 9999));
  idReading["unit"] = "id";
  
  // Equipment ID reading
  JsonObject eqReading = readings.createNestedObject();
  eqReading["sensor_type"] = "equipment_id";
  eqReading["value"] = "EQ_" + String(random(100, 999)) + "_" + String(random(0x10000000, 0xFFFFFFFF), HEX);
  eqReading["unit"] = "id";
  
  // Encrypt ALL sensor values for industrial IoT security
  encryptAllReadings(readings);
  
  // Send the encrypted payload
  String payload;
  serializeJson(doc, payload);
  
  webSocket.sendTXT(payload);
  Serial.printf("📤 Sent encrypted payload with %d readings\n", readings.size());
}

void encryptAllReadings(JsonArray& readings) {
  for (JsonObject reading : readings) {
    String sensorType = reading["sensor_type"];
    String originalValue = reading["value"];
    
    // Encrypt the value
    String encryptedValue = encryptField(originalValue);
    
    if (!encryptedValue.isEmpty()) {
      reading["value"] = encryptedValue;
      reading["encrypted"] = true;
      Serial.printf("🔒 Encrypted %s sensor value\n", sensorType.c_str());
    } else {
      Serial.printf("❌ Failed to encrypt %s sensor value\n", sensorType.c_str());
    }
  }
}

String encryptField(const String& plaintext) {
  if (plaintext.length() == 0) {
    return "";
  }
  
  // Generate random IV (16 bytes)
  byte iv[16];
  RNG.rand(iv, 16);
  
  // Prepare plaintext for encryption (add PKCS7 padding)
  String paddedText = addPKCS7Padding(plaintext);
  
  // Encrypt
  aes256cbc.clear();
  aes256cbc.setKey(deviceKey, 32);
  aes256cbc.setIV(iv, 16);
  
  byte* plaintextBytes = (byte*)paddedText.c_str();
  int plaintextLen = paddedText.length();
  byte* ciphertext = new byte[plaintextLen];
  
  aes256cbc.encrypt(ciphertext, plaintextBytes, plaintextLen);
  
  // Combine IV + ciphertext
  byte* combined = new byte[16 + plaintextLen];
  memcpy(combined, iv, 16);
  memcpy(combined + 16, ciphertext, plaintextLen);
  
  // Encode to Base64
  String result = base64Encode(combined, 16 + plaintextLen);
  
  // Cleanup
  delete[] ciphertext;
  delete[] combined;
  
  return result;
}

String addPKCS7Padding(const String& data) {
  int blockSize = 16;
  int padding = blockSize - (data.length() % blockSize);
  
  String paddedData = data;
  for (int i = 0; i < padding; i++) {
    paddedData += (char)padding;
  }
  
  return paddedData;
}

String base64Encode(const byte* data, size_t len)
{
    /* get space required for the ASCII result */
    const uint16_t outLen = encode_base64_length(len);          // helper in v1.3.0

    /* allocate output as UNSIGNED char buffer */
    uint8_t* out = new uint8_t[outLen + 1];                     // +1 for '\0'

    /* encode: (input, input_len, output) – all unsigned char*  */
    encode_base64((uint8_t*)data, len, out);                    // ← no -fpermissive error

    out[outLen] = '\0';                                         // null‑terminate

    String s((char*)out);                                       // build Arduino String
    delete[] out;
    return s;
}

// Optional: Read real sensor data (uncomment if you have DHT22 connected)
/*
#include <DHT.h>
#define DHT_PIN 4
#define DHT_TYPE DHT22
DHT dht(DHT_PIN, DHT_TYPE);

float readTemperature() {
  return dht.readTemperature();
}

float readHumidity() {
  return dht.readHumidity();
}
*/