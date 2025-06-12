"""
Django Backend Encryption Utilities
Handles RSA/AES encryption for secure authentication
"""

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import json
import os
from django.core.cache import cache


class EncryptionManager:
    def __init__(self):
        self.backend = default_backend()
        self._private_key = None
        self._public_key = None
        self._load_or_generate_keypair()
    
    def _load_or_generate_keypair(self):
        """Load existing keypair or generate new one"""
        try:
            # Try to load from cache first
            private_key_pem = cache.get('rsa_private_key')
            public_key_pem = cache.get('rsa_public_key')
            
            if private_key_pem and public_key_pem:
                self._private_key = serialization.load_pem_private_key(
                    private_key_pem.encode(), 
                    password=None, 
                    backend=self.backend
                )
                self._public_key = self._private_key.public_key()
                return
                
            # Generate new keypair
            self._generate_keypair()
            
        except Exception as e:
            print(f"Error loading keypair: {e}")
            self._generate_keypair()
    
    def _generate_keypair(self):
        """Generate new RSA keypair"""
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=self.backend
        )
        self._public_key = self._private_key.public_key()
        
        # Cache the keys (expires in 1 hour)
        private_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        
        public_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
        cache.set('rsa_private_key', private_pem, 3600)  # 1 hour
        cache.set('rsa_public_key', public_pem, 3600)   # 1 hour
    
    def get_public_key_pem(self):
        """Get public key in PEM format for frontend"""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
    
    def decrypt_rsa(self, encrypted_data_b64):
        """Decrypt RSA encrypted data"""
        try:
            encrypted_data = base64.b64decode(encrypted_data_b64)
            decrypted = self._private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return decrypted.decode('utf-8')
        except Exception as e:
            raise ValueError(f"RSA decryption failed: {e}")
    
    def decrypt_aes(self, encrypted_data, key_hex, iv_hex):
        """Decrypt AES encrypted data"""
        try:
            key = bytes.fromhex(key_hex)
            iv = bytes.fromhex(iv_hex)
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=self.backend
            )
            decryptor = cipher.decryptor()
            decrypted_padded = decryptor.update(encrypted_bytes) + decryptor.finalize()
            
            # Remove PKCS7 padding
            padding_length = decrypted_padded[-1]
            decrypted = decrypted_padded[:-padding_length]
            
            return decrypted.decode('utf-8')
        except Exception as e:
            raise ValueError(f"AES decryption failed: {e}")
    
    def decrypt_form_data(self, encrypted_payload):
        """Decrypt form data from frontend"""
        try:
            # Extract components
            data = encrypted_payload.get('data', {})
            encrypted_aes_key = encrypted_payload.get('key')
            iv_hex = encrypted_payload.get('iv')
            
            if not all([encrypted_aes_key, iv_hex]):
                raise ValueError("Missing encryption components")
            
            # Decrypt AES key using RSA
            aes_key_hex = self.decrypt_rsa(encrypted_aes_key)
            
            # Decrypt sensitive fields
            decrypted_data = {}
            for field, value in data.items():
                if isinstance(value, dict) and value.get('encrypted'):
                    # Decrypt this field
                    decrypted_data[field] = self.decrypt_aes(
                        value['data'], 
                        aes_key_hex, 
                        iv_hex
                    )
                else:
                    # Field is not encrypted
                    decrypted_data[field] = value
            
            return decrypted_data
            
        except Exception as e:
            raise ValueError(f"Form data decryption failed: {e}")

    def decrypt_request_data(self, encrypted_data):
        """
        Decrypt request data from frontend
        Expected format: {'data': {...}, 'key': 'base64_encrypted_key', 'iv': 'hex_iv'}
        """
        try:
            # Extract components
            encrypted_form_data = encrypted_data.get('data', {})
            encrypted_aes_key_b64 = encrypted_data.get('key')
            iv_hex = encrypted_data.get('iv')
            
            if not all([encrypted_aes_key_b64, iv_hex]):
                return None
            
            # Decrypt AES key with RSA private key
            encrypted_aes_key = base64.b64decode(encrypted_aes_key_b64)
            aes_key_hex = self._private_key.decrypt(
                encrypted_aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            ).decode('utf-8')
            
            # Convert hex key back to bytes
            aes_key = bytes.fromhex(aes_key_hex)
            iv = bytes.fromhex(iv_hex)
            
            # Decrypt each encrypted field
            decrypted_data = {}
            for field, value in encrypted_form_data.items():
                if isinstance(value, dict) and value.get('encrypted'):
                    # Decrypt this field
                    encrypted_value_b64 = value.get('data')
                    if encrypted_value_b64:
                        decrypted_value = self.decrypt_aes(encrypted_value_b64, aes_key_hex, iv_hex)
                        decrypted_data[field] = decrypted_value
                else:
                    # Plain field
                    decrypted_data[field] = value
            
            return decrypted_data
            
        except Exception as e:
            print(f"Decryption error: {e}")
            return None


# Global instance
encryption_manager = EncryptionManager() 