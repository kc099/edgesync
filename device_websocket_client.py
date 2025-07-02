import os
import asyncio
import json
import random
import uuid

import websockets

"""Simple demo client to publish sensor data via WebSocket to the EdgeSync backend.

Usage:
    export DEVICE_TOKEN=<YOUR_DEVICE_TOKEN>
    # Optional overrides
    export WS_URL=ws://localhost:8000/ws/sensors/
    python device_websocket_client.py

The script will connect to <WS_URL>?token=<DEVICE_TOKEN> and every 2 seconds send a
random temperature reading.
"""

WS_URL = os.getenv("WS_URL", "ws://localhost:8000/ws/sensors/")
# Obtain the device token from environment variable – no hard-coded secrets
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN")  # must be provided via env
SEND_INTERVAL = float(os.getenv("SEND_INTERVAL", "2"))  # seconds

if not DEVICE_TOKEN:
    raise RuntimeError("Please set the DEVICE_TOKEN environment variable to your device's auth token.")

async def publish_sensor_data(token: str, ws_url: str):
    """Connect and continually publish random sensor readings."""
    url = f"{ws_url}?token={token}"
    # Use the device token as the logical device_id so the backend / dashboard
    # can consistently correlate incoming data with this physical device.
    device_id = token

    async with websockets.connect(url, ping_interval=None) as websocket:
        print(f"Connected to {url}. Publishing data every {SEND_INTERVAL}s ... (Ctrl+C to stop)")
        try:
            while True:
                payload = {
                    "device_id": device_id,
                    "sensor_type": "temperature",
                    "value": round(random.uniform(20.0, 30.0), 2),
                    "unit": "C"
                }
                await websocket.send(json.dumps(payload))
                await asyncio.sleep(SEND_INTERVAL)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            print("Interrupted by user. Closing connection…")


def main():
    asyncio.run(publish_sensor_data(DEVICE_TOKEN, WS_URL))


if __name__ == "__main__":
    main() 