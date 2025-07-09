#!/usr/bin/env python3
"""
Test WebSocket client for WidgetDataConsumer
"""
import asyncio
import json
import websockets
import sys

# Test JWT token (replace with a valid one from your app)
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzUyMDQ2MDY5LCJpYXQiOjE3NTIwMzg3MTksImp0aSI6IjFiNTRiNjI5ZmE0MzRiN2M4YTIwOGZjN2FlMGJlZGMzIiwidXNlcl9pZCI6NH0.0rljbfuJLtYVQJ8Es2MWmKU92p5CzC2sXGrHcAGw0Fk"

WIDGET_ID = "flow-widget-20250709-062504-ba30ffd4"
WS_URL = f"ws://localhost:8000/ws/widgets/{WIDGET_ID}/?token={TEST_TOKEN}"

async def test_widget_websocket():
    """Test the widget WebSocket connection"""
    print(f"Connecting to: {WS_URL}")
    
    try:
        async with websockets.connect(WS_URL, ping_interval=None) as websocket:
            print("✅ Connected successfully!")
            print("Waiting for messages... (Press Ctrl+C to quit)")
            
            # Keep the connection alive and listen for messages
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        print(f"📨 Received: {data}")
                    except json.JSONDecodeError:
                        print(f"📨 Raw message: {message}")
            except websockets.exceptions.ConnectionClosed as e:
                print(f"❌ Connection closed: {e}")
            except KeyboardInterrupt:
                print("\n👋 Disconnecting...")
                
    except websockets.exceptions.InvalidURI as e:
        print(f"❌ Invalid URI: {e}")
    except websockets.exceptions.InvalidHandshake as e:
        print(f"❌ Handshake failed: {e}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ Connection closed immediately: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    print("🧪 Testing Widget WebSocket Connection")
    print("=" * 50)
    asyncio.run(test_widget_websocket()) 