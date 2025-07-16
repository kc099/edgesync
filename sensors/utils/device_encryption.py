"""
Device-specific encryption utilities for IoT sensor data
Provides efficient field-level encryption for high-frequency sensor transmissions
"""

import base64
import json
import secrets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding as crypto_padding
import logging

logger = logging.getLogger(__name__)

# Try to import Django components, fallback if not available
try:
    from django.core.cache import cache
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    cache = None

class DeviceEncryptionManager:
    """Manages encryption for individual IoT devices"""
    
    def __init__(self):
        self.backend = default_backend()
    
    def generate_device_key(self, device_uuid):
        """Generate a unique AES-256 key for a device"""
        # Generate 32-byte (256-bit) key
        device_key = secrets.token_bytes(32)
        
        # Cache the key with device UUID (expires in 24 hours) if Django cache available
        if DJANGO_AVAILABLE and cache:
            cache_key = f"device_encryption_key_{device_uuid}"
            cache.set(cache_key, base64.b64encode(device_key).decode(), 86400)
        
        return device_key
    
    def get_device_key(self, device_uuid):
        """Retrieve device's encryption key"""
        if DJANGO_AVAILABLE and cache:
            cache_key = f"device_encryption_key_{device_uuid}"
            key_b64 = cache.get(cache_key)
            
            if key_b64:
                return base64.b64decode(key_b64)
        
        # Generate new key if cache not available or key not found
        return self.generate_device_key(device_uuid)
    
    def encrypt_sensor_values(self, data, device_key):
        """
        Encrypt only sensitive sensor values while preserving JSON structure
        
        Input: {
            "device_id": "uuid",
            "readings": [
                {"sensor_type": "temperature", "value": 25.4, "unit": "C"},
                {"sensor_type": "location", "value": "40.7128,-74.0060", "unit": "lat,lng"}
            ]
        }
        
        Output: {
            "device_id": "uuid",
            "readings": [
                {"sensor_type": "temperature", "value": "encrypted_base64", "unit": "C", "encrypted": true},
                {"sensor_type": "location", "value": "encrypted_base64", "unit": "lat,lng", "encrypted": true}
            ]
        }
        """
        try:
            # Define which sensor types should be encrypted
            try:
                from django.conf import settings
                sensitive_sensors = getattr(settings, 'ENCRYPTED_SENSOR_TYPES', [
                    'location', 'gps', 'camera', 'microphone', 'biometric', 
                    'personal', 'sensitive', 'private'
                ])
            except (ImportError, Exception):
                # Fallback for non-Django environments or missing settings
                sensitive_sensors = [
                    'location', 'gps', 'camera', 'microphone', 'biometric', 
                    'personal', 'sensitive', 'private'
                ]
            
            # Clone the data to avoid modifying original
            encrypted_data = json.loads(json.dumps(data))
            
            if "readings" in encrypted_data:
                for reading in encrypted_data["readings"]:
                    sensor_type = reading.get("sensor_type", "").lower()
                    
                    # Check if this sensor type should be encrypted
                    if any(sensitive in sensor_type for sensitive in sensitive_sensors):
                        original_value = str(reading["value"])
                        encrypted_value = self._encrypt_field(original_value, device_key)
                        
                        reading["value"] = encrypted_value
                        reading["encrypted"] = True
                        
                        logger.debug(f"Encrypted {sensor_type} sensor value")
            
            elif "value" in encrypted_data:
                # Single reading format
                sensor_type = encrypted_data.get("sensor_type", "").lower()
                if any(sensitive in sensor_type for sensitive in sensitive_sensors):
                    original_value = str(encrypted_data["value"])
                    encrypted_data["value"] = self._encrypt_field(original_value, device_key)
                    encrypted_data["encrypted"] = True
            
            return encrypted_data
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            # Return original data if encryption fails (graceful degradation)
            return data
    
    def decrypt_sensor_values(self, data, device_key):
        """
        Decrypt encrypted sensor values while preserving JSON structure
        """
        try:
            # Clone the data to avoid modifying original
            decrypted_data = json.loads(json.dumps(data))
            
            if "readings" in decrypted_data:
                for reading in decrypted_data["readings"]:
                    if reading.get("encrypted"):
                        encrypted_value = reading["value"]
                        decrypted_value = self._decrypt_field(encrypted_value, device_key)
                        
                        # Try to convert back to number if possible
                        try:
                            reading["value"] = float(decrypted_value)
                        except ValueError:
                            reading["value"] = decrypted_value
                        
                        # Remove encryption flag
                        del reading["encrypted"]
                        
            elif decrypted_data.get("encrypted"):
                # Single reading format
                encrypted_value = decrypted_data["value"]
                decrypted_value = self._decrypt_field(encrypted_value, device_key)
                
                try:
                    decrypted_data["value"] = float(decrypted_value)
                except ValueError:
                    decrypted_data["value"] = decrypted_value
                
                del decrypted_data["encrypted"]
            
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            # Return original data if decryption fails
            return data
    
    def _encrypt_field(self, plaintext, key):
        """Encrypt a single field value"""
        # Generate random IV for each encryption
        iv = secrets.token_bytes(16)
        
        # Create cipher
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=self.backend)
        encryptor = cipher.encryptor()
        
        # Add PKCS7 padding
        padder = crypto_padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext.encode()) + padder.finalize()
        
        # Encrypt
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # Combine IV + ciphertext and encode as base64
        encrypted_bytes = iv + ciphertext
        return base64.b64encode(encrypted_bytes).decode()
    
    def _decrypt_field(self, encrypted_b64, key):
        """Decrypt a single field value"""
        # Decode from base64
        encrypted_bytes = base64.b64decode(encrypted_b64)
        
        # Extract IV and ciphertext
        iv = encrypted_bytes[:16]
        ciphertext = encrypted_bytes[16:]
        
        # Create cipher
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=self.backend)
        decryptor = cipher.decryptor()
        
        # Decrypt
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Remove PKCS7 padding
        unpadder = crypto_padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
        
        return plaintext.decode()

# Global instance
device_encryption_manager = DeviceEncryptionManager()
