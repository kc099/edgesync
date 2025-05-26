#!/usr/bin/env python3
"""
ESP32 Simulator for testing the WebSocket sensor dashboard.
This script simulates multiple ESP32 devices sending sensor data.
"""

import asyncio
import websockets
import json
import random
import time
from datetime import datetime

class ESP32Simulator:
    def __init__(self, device_id, websocket_url="ws://localhost:8000/ws/sensors/"):
        self.device_id = device_id
        self.websocket_url = websocket_url
        self.sensors = {
            'temperature': {'min': 18.0, 'max': 35.0, 'unit': '°C'},
            'humidity': {'min': 30.0, 'max': 80.0, 'unit': '%'},
            'pressure': {'min': 980.0, 'max': 1020.0, 'unit': 'hPa'},
            'light': {'min': 0.0, 'max': 1000.0, 'unit': 'lux'},
        }
        
    async def connect_and_send_data(self):
        """Connect to WebSocket and send sensor data periodically"""
        try:
            async with websockets.connect(self.websocket_url) as websocket:
                print(f"✅ {self.device_id} connected to {self.websocket_url}")
                
                while True:
                    # Send data for each sensor type
                    for sensor_type, config in self.sensors.items():
                        # Generate realistic sensor data with some variation
                        value = round(random.uniform(config['min'], config['max']), 2)
                        
                        data = {
                            'device_id': self.device_id,
                            'sensor_type': sensor_type,
                            'value': value,
                            'unit': config['unit']
                        }
                        
                        # Send data
                        await websocket.send(json.dumps(data))
                        print(f"📤 {self.device_id}: {sensor_type} = {value} {config['unit']}")
                        
                        # Wait for response
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            response_data = json.loads(response)
                            if response_data.get('status') == 'success':
                                print(f"✅ {self.device_id}: Data saved with ID {response_data.get('id')}")
                            else:
                                print(f"❌ {self.device_id}: Error - {response_data.get('message')}")
                        except asyncio.TimeoutError:
                            print(f"⏰ {self.device_id}: No response received")
                        except json.JSONDecodeError:
                            print(f"❌ {self.device_id}: Invalid response format")
                    
                    # Wait before sending next batch
                    await asyncio.sleep(random.uniform(5, 15))  # Random interval 5-15 seconds
                    
        except websockets.exceptions.ConnectionClosed:
            print(f"❌ {self.device_id}: Connection closed")
        except Exception as e:
            print(f"❌ {self.device_id}: Error - {e}")

async def simulate_multiple_devices():
    """Simulate multiple ESP32 devices"""
    devices = [
        ESP32Simulator("ESP32_Kitchen"),
        ESP32Simulator("ESP32_LivingRoom"),
        ESP32Simulator("ESP32_Bedroom"),
        ESP32Simulator("ESP32_Garage"),
    ]
    
    print("🚀 Starting ESP32 simulation...")
    print("📡 Devices:", [device.device_id for device in devices])
    print("🌐 WebSocket URL: ws://localhost:8000/ws/sensors/")
    print("⏹️  Press Ctrl+C to stop\n")
    
    # Run all devices concurrently
    tasks = [device.connect_and_send_data() for device in devices]
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n🛑 Simulation stopped by user")
    except Exception as e:
        print(f"\n❌ Simulation error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 ESP32 Sensor Dashboard - Device Simulator")
    print("=" * 60)
    print("This script simulates multiple ESP32 devices sending sensor data")
    print("Make sure your Django server is running on localhost:8000")
    print("=" * 60)
    
    # Check if we should use a different WebSocket URL
    import sys
    if len(sys.argv) > 1:
        websocket_url = sys.argv[1]
        print(f"Using custom WebSocket URL: {websocket_url}")
        # Update the default URL for all devices
        ESP32Simulator.__init__ = lambda self, device_id, websocket_url=websocket_url: setattr(self, 'device_id', device_id) or setattr(self, 'websocket_url', websocket_url) or setattr(self, 'sensors', {
            'temperature': {'min': 18.0, 'max': 35.0, 'unit': '°C'},
            'humidity': {'min': 30.0, 'max': 80.0, 'unit': '%'},
            'pressure': {'min': 980.0, 'max': 1020.0, 'unit': 'hPa'},
            'light': {'min': 0.0, 'max': 1000.0, 'unit': 'lux'},
        })
    
    try:
        asyncio.run(simulate_multiple_devices())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!") 