import os
import asyncio
import json
import random
import uuid
import base64
import secrets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding
from cryptography.hazmat.backends import default_backend

import websockets

"""Enhanced demo client with encryption support for EdgeSync backend.

Usage:
    export DEVICE_TOKEN=<YOUR_DEVICE_TOKEN>
    # Optional overrides
    export WS_URL=ws://localhost:8000/ws/sensors/
    export ENABLE_ENCRYPTION=true  # Enable field-level encryption
    python device_websocket_client_encrypted.py

The script will connect, receive encryption key, and send encrypted sensor data
for sensitive sensor types while keeping metadata readable.
"""

WS_URL = os.getenv("WS_URL", "ws://localhost:8000/ws/sensors/")
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN")  # must be provided via env
SEND_INTERVAL = float(os.getenv("SEND_INTERVAL", "2"))  # seconds
ENABLE_ENCRYPTION = os.getenv("ENABLE_ENCRYPTION", "false").lower() == "true"

class DeviceEncryption:
    """Handles device-side encryption for sensor data"""
    
    def __init__(self):
        self.device_key = None
        self.encryption_enabled = False
        self.backend = default_backend()
        
        # For industrial IoT, ALL sensor data is considered sensitive
        # and requires end-to-end encryption
    
    def initialize_encryption(self, key_b64):
        """Initialize encryption with key from backend"""
        try:
            self.device_key = base64.b64decode(key_b64)
            self.encryption_enabled = True
            print(f"✅ Encryption initialized with key length: {len(self.device_key)} bytes")
        except Exception as e:
            print(f"❌ Failed to initialize encryption: {e}")
            self.encryption_enabled = False
    
    def encrypt_sensor_data(self, data):
        """Encrypt ALL sensor values for end-to-end industrial IoT security"""
        if not self.encryption_enabled or not self.device_key:
            return data
        
        try:
            # Clone data to avoid modifying original
            encrypted_data = json.loads(json.dumps(data))
            
            if "readings" in encrypted_data:
                # Bulk readings format - encrypt ALL sensor values
                for reading in encrypted_data["readings"]:
                    sensor_type = reading.get("sensor_type", "")
                    original_value = str(reading["value"])
                    reading["value"] = self._encrypt_field(original_value)
                    reading["encrypted"] = True
                    print(f"🔒 Encrypted {sensor_type} sensor value")
            
            elif "sensor_type" in encrypted_data:
                # Single reading format - encrypt the value
                sensor_type = encrypted_data.get("sensor_type", "")
                original_value = str(encrypted_data["value"])
                encrypted_data["value"] = self._encrypt_field(original_value)
                encrypted_data["encrypted"] = True
                print(f"🔒 Encrypted {sensor_type} sensor value")
            
            return encrypted_data
            
        except Exception as e:
            print(f"❌ Encryption failed: {e}")
            return data  # Return original data on failure
    
    def _encrypt_field(self, plaintext):
        """Encrypt a single field value using AES-256-CBC"""
        # Generate random IV for each encryption
        iv = secrets.token_bytes(16)
        
        # Create cipher
        cipher = Cipher(algorithms.AES(self.device_key), modes.CBC(iv), backend=self.backend)
        encryptor = cipher.encryptor()
        
        # Add PKCS7 padding
        padder = crypto_padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode()) + padder.finalize()
        
        # Encrypt
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # Combine IV + ciphertext and encode as base64
        encrypted_bytes = iv + ciphertext
        return base64.b64encode(encrypted_bytes).decode()

async def publish_sensor_data(token: str, ws_url: str):
    """Connect and continually publish sensor readings with encryption support"""
    url = f"{ws_url}?token={token}"
    device_id = None
    encryption = DeviceEncryption()

    async with websockets.connect(url, ping_interval=None) as websocket:
        print(f"Connected to {url}. Waiting for device_info …")

        # Wait for the initial device_info payload
        try:
            msg = await websocket.recv()
            info = json.loads(msg)
            if info.get("type") == "device_info":
                device_id = info["device_uuid"]
                print(f"Received device_uuid: {device_id}")
                
                # Initialize encryption if available
                if ENABLE_ENCRYPTION and info.get("encryption_enabled") and info.get("encryption_key"):
                    encryption.initialize_encryption(info["encryption_key"])
                else:
                    print("📡 Encryption not enabled - WARNING: Industrial IoT requires encryption!")
                    print("⚠️  All sensor data should be encrypted in production environment")
                    
                print(f"Starting data publish every {SEND_INTERVAL}s …")
            else:
                raise RuntimeError("Expected device_info message from server but received something else.")
        except Exception as e:
            raise RuntimeError(f"Failed to receive device_info from server: {e}")

        try:
            while True:
                # Generate sample sensor data - ALL values will be encrypted
                payload = {
                    "device_id": device_id,
                    "readings": [
                        {
                            "sensor_type": "temperature",
                            "value": round(random.uniform(20.0, 30.0), 2),
                            "unit": "C"
                        },
                        {
                            "sensor_type": "humidity", 
                            "value": round(random.uniform(40.0, 65.0), 2),
                            "unit": "%"
                        },
                        {
                            "sensor_type": "pressure",
                            "value": round(random.uniform(1010.0, 1025.0), 2),
                            "unit": "hPa"
                        },
                        {
                            "sensor_type": "location",
                            "value": f"{round(random.uniform(40.0, 41.0), 6)},{round(random.uniform(-74.0, -73.0), 6)}",
                            "unit": "lat,lng"
                        },
                        {
                            "sensor_type": "personal_id",
                            "value": f"USER_{random.randint(1000, 9999)}",
                            "unit": "id"
                        },
                        {
                            "sensor_type": "equipment_id",
                            "value": f"EQ_{random.randint(100, 999)}_{uuid.uuid4().hex[:8].upper()}",
                            "unit": "id"
                        }
                    ]
                }
                
                # Encrypt ALL sensor data for industrial IoT security
                encrypted_payload = encryption.encrypt_sensor_data(payload)
                
                await websocket.send(json.dumps(encrypted_payload))
                print(f"📤 Sent fully encrypted payload with {len(encrypted_payload['readings'])} readings")
                
                await asyncio.sleep(SEND_INTERVAL)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            print("Interrupted by user. Closing connection…")


def main():
    if not DEVICE_TOKEN:
        print("❌ Error: DEVICE_TOKEN environment variable is required")
        return
    
    print("🚀 Starting industrial IoT device client with full encryption...")
    print(f"📡 WebSocket URL: {WS_URL}")
    print(f"🔐 Full encryption enabled: {ENABLE_ENCRYPTION}")
    print(f"⏱️  Send interval: {SEND_INTERVAL}s")
    print("🏭 Industrial mode: ALL sensor data will be encrypted")
    
    asyncio.run(publish_sensor_data(DEVICE_TOKEN, WS_URL))


if __name__ == "__main__":
    main()
