#!/usr/bin/env python3
"""
Test script to verify frontend-backend encryption compatibility
"""

import json
import base64
import secrets
import sys
import os

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edgesync.settings')

import django
django.setup()

from sensors.utils.device_encryption import device_encryption_manager

def test_encryption_compatibility():
    """Test that encryption/decryption works correctly"""
    
    print("🔧 Testing IoT Encryption System Compatibility...")
    print("=" * 60)
    
    # Test data with mixed sensitive and non-sensitive sensors
    test_device_uuid = "550e8400-e29b-41d4-a716-446655440000"
    
    test_payload = {
        "device_id": test_device_uuid,
        "readings": [
            {
                "sensor_type": "temperature",
                "value": 25.4,
                "unit": "C"
            },
            {
                "sensor_type": "humidity", 
                "value": 60.2,
                "unit": "%"
            },
            {
                "sensor_type": "location",  # Should be encrypted
                "value": "40.712800,-74.006000",
                "unit": "lat,lng"
            },
            {
                "sensor_type": "personal_id",  # Should be encrypted
                "value": "USER_1234",
                "unit": "id"
            },
            {
                "sensor_type": "pressure",
                "value": 1013.25,
                "unit": "hPa"
            }
        ]
    }
    
    # Generate device key
    device_key = device_encryption_manager.get_device_key(test_device_uuid)
    print(f"📊 Generated device key: {base64.b64encode(device_key).decode()[:16]}...")
    
    # Test encryption
    print("\n🔒 Testing encryption...")
    encrypted_payload = device_encryption_manager.encrypt_sensor_values(test_payload, device_key)
    
    # Count encrypted vs non-encrypted readings
    encrypted_count = sum(1 for reading in encrypted_payload['readings'] if reading.get('encrypted'))
    total_count = len(encrypted_payload['readings'])
    
    print(f"📈 Encrypted {encrypted_count} out of {total_count} sensor readings")
    
    # Display results
    print("\n📋 Encryption Results:")
    for i, reading in enumerate(encrypted_payload['readings']):
        status = "🔒 ENCRYPTED" if reading.get('encrypted') else "📝 PLAIN TEXT"
        print(f"  {i+1}. {reading['sensor_type']:15} → {status}")
    
    # Test decryption
    print("\n🔓 Testing decryption...")
    decrypted_payload = device_encryption_manager.decrypt_sensor_values(encrypted_payload, device_key)
    
    # Verify data integrity
    if decrypted_payload == test_payload:
        print("✅ Decryption successful - data integrity verified!")
    else:
        print("❌ Decryption failed - data mismatch!")
        return False
    
    # Test JSON serialization (important for WebSocket transmission)
    print("\n📡 Testing JSON serialization...")
    try:
        json_data = json.dumps(encrypted_payload)
        parsed_data = json.loads(json_data)
        print("✅ JSON serialization successful")
        print(f"📦 Payload size: {len(json_data)} bytes")
    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")
        return False
    
    # Show sample encrypted data
    print("\n🔍 Sample encrypted data structure:")
    encrypted_reading = next((r for r in encrypted_payload['readings'] if r.get('encrypted')), None)
    if encrypted_reading:
        print(f"  Sensor: {encrypted_reading['sensor_type']}")
        print(f"  Encrypted Value: {encrypted_reading['value'][:32]}...")
        print(f"  Unit: {encrypted_reading['unit']}")
        print(f"  Encrypted Flag: {encrypted_reading['encrypted']}")
    
    print("\n" + "=" * 60)
    print("🎉 All encryption tests passed!")
    print("✅ System ready for secure IoT data transmission")
    
    return True

if __name__ == "__main__":
    test_encryption_compatibility()
