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

# The device UUID will be provided by the backend once the WebSocket
# connection is authenticated. We store it after receiving the first
# "device_info" message.

async def publish_sensor_data(token: str, ws_url: str):
    """Connect and continually publish random sensor readings."""
    url = f"{ws_url}?token={token}"
    device_id = None  # Will be filled after receiving device_info

    async with websockets.connect(url, ping_interval=None) as websocket:
        print(f"Connected to {url}. Waiting for device_info …")

        # Wait for the initial device_info payload to learn our UUID
        try:
            msg = await websocket.recv()
            info = json.loads(msg)
            if info.get("type") == "device_info":
                device_id = info["device_uuid"]
                print(f"Received device_uuid: {device_id}. Starting data publish every {SEND_INTERVAL}s …")
            else:
                raise RuntimeError("Expected device_info message from server but received something else.")
        except Exception as e:
            raise RuntimeError(f"Failed to receive device_info from server: {e}")

        try:
            while True:
                payload = {
                    "device_id": device_id,
                    # Send multiple sensor readings in one message
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
                        }
                    ]
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