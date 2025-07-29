This is a comprehensive task. Let's break it down.

  First, I'll analyze the backend code to understand the data flow and encryption. I'll start with the
   WebSocket consumer in the sensors app, as that's where the device connects. I'll look for the
  authentication, decryption, and broadcasting logic.

  Next, I'll investigate the frontend. I'll start by searching for WebSocket connection logic in the
  das directory. Based on the file names, useDeviceWidgetData.js seems like a good place to start.
  I'll also check FlowEditor.js and the dashboard-related components to see how they consume the data.


✦ consumers.py seems like the right place for WebSocket logic. I'll read it to understand connection
  handling, authentication, and data processing.

✦ Here's what I've gathered from consumers.py:

   * Two Consumers: There are two consumers: SensorDataConsumer for devices and WidgetDataConsumer for
     the frontend widgets.
   * Authentication:
       * SensorDataConsumer authenticates devices via a DEVICE_TOKEN in the query string. It can also
         handle JWTs for user-based connections.
       * WidgetDataConsumer authenticates frontend clients (widgets) via a JWT in the query string.
   * Encryption:
       * When a device connects, the SensorDataConsumer generates or retrieves a device-specific
         encryption key using device_encryption_manager.get_device_key.
       * It sends this key back to the device in a device_info message.
       * Incoming data from the device is decrypted using
         device_encryption_manager.decrypt_sensor_values.
   * Data Flow:
       1. An encrypted payload is sent from the device to the SensorDataConsumer.
       2. The consumer decrypts the data.
       3. The decrypted data is broadcast to two places:
           * The sensor_data group, which seems to be a general-purpose firehose of all sensor data.
           * A widget-specific group (widget_{tv.widget_id}) if the data is being tracked by a widget.
             This is handled by _handle_widget_tracking.
       4. The WidgetDataConsumer listens on the widget-specific group and forwards the data to the
          subscribed frontend component.

  Now, let's look at the frontend. I'll start with useDeviceWidgetData.js to see how it handles
  WebSocket connections.

✦ The useDeviceWidgetData.js hook confirms my understanding of the frontend.

   * WebSocket Connection: It establishes a WebSocket connection to ws/widgets/{widget.id} with the
     JWT access token in the query string. This matches the WidgetDataConsumer on the backend.
   * Data Handling:
       * The onmessage handler receives the data.
       * It calls deviceEncryption.decryptSensorData(rawData) to decrypt the payload.
       * The decrypted data is then transformed and added to the component's state.
   * Encryption: The frontend uses a IoTEncryptionManager to handle decryption. I'll need to examine
     src/utils/iotEncryption.js to see the decryption logic.

  Now, let's look at the IoTEncryptionManager.

✦ The iotEncryption.js file reveals the final piece of the puzzle. It uses crypto-js to perform
  AES-256-CBC encryption and decryption, which is compatible with the Python cryptography library used
  on the backend.

  Here's the complete data flow:

   1. Device Connection: The Python script (device_websocket_client_encrypted.py) connects to the
      SensorDataConsumer in edgesync with its DEVICE_TOKEN.
   2. Key Exchange: The SensorDataConsumer generates a device-specific AES key, stores it, and sends
      the base64-encoded key back to the device.
   3. Encryption (Device): The Python script receives the key and uses it to encrypt sensor data with
      AES-256-CBC. It prepends a 16-byte IV to the ciphertext and base64-encodes the result.
   4. Data Transmission: The encrypted payload is sent to the SensorDataConsumer.
   5. Decryption (Backend): The SensorDataConsumer uses the stored device key to decrypt the payload.
      It extracts the IV, decrypts the ciphertext, and unpads the plaintext.
   6. Backend Broadcast: The decrypted data is broadcast to two channel groups:
       * sensor_data: A general firehose of all data.
       * widget_{widget_id}: A specific group for each widget that is tracking that particular data
         stream.
   7. Frontend Connection: The React frontend, specifically the useDeviceWidgetData hook, connects to
      the WidgetDataConsumer using a WebSocket, authenticating with a JWT. It subscribes to the
      widget_{widget_id} group.
   8. Frontend Reception: The WidgetDataConsumer receives the broadcasted data and sends it to the
      connected useDeviceWidgetData hook.
   9. Decryption (Frontend): The onmessage handler in useDeviceWidgetData calls iotEncryption.js's
      decryptSensorData function. This function is not actually decrypting anything, because the data
      is already decrypted by the backend. It seems to be a leftover from a previous implementation
      where the frontend was responsible for decryption.
   10. Display: The useDeviceWidgetData hook updates its state with the new data, which causes the
       widget component to re-render and display the latest information.

  Summary of Files:

   * `edgesync/device_websocket_client_encrypted.py`: The device client that sends encrypted data.
   * `edgesync/sensors/consumers.py`: The Django Channels consumer that handles WebSocket connections,
     authentication, decryption, and broadcasting.
   * `das/src/hooks/useDeviceWidgetData.js`: The React hook that connects to the WebSocket, receives
     data, and updates the UI.
   * `das/src/utils/iotEncryption.js`: The frontend utility for encryption/decryption. Although it has
     decryption logic, it's not currently used for that purpose in the data flow, as the backend
     handles decryption.

  This covers the entire flow from the device to the dashboard.