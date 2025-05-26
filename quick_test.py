#!/usr/bin/env python3
"""
Quick test script to verify WebSocket connection and send test data.
"""

import asyncio
import websockets
import json

async def test_websocket():
    """Test WebSocket connection and send sample data"""
    uri = "ws://localhost:8000/ws/sensors/"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket server")
            
            # Send test sensor data
            test_data = {
                "device_id": "TEST_ESP32",
                "sensor_type": "temperature",
                "value": 25.5,
                "unit": "°C"
            }
            
            await websocket.send(json.dumps(test_data))
            print(f"📤 Sent: {test_data}")
            
            # Wait for response
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"📥 Received: {response_data}")
            
            if response_data.get('status') == 'success':
                print("✅ Test successful! Data was saved to database.")
            else:
                print("❌ Test failed!")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure the Django server is running on localhost:8000")

if __name__ == "__main__":
    print("🧪 Testing WebSocket connection...")
    asyncio.run(test_websocket()) 