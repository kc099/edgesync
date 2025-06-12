#!/usr/bin/env python3
import requests
import json
import base64
import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

def test_encrypted_login():
    # Get public key
    response = requests.get('http://localhost:8000/api/public-key/')
    public_key_pem = response.json()['public_key']
    
    # Load public key
    public_key = serialization.load_pem_public_key(public_key_pem.encode(), backend=default_backend())
    
    # Generate AES key
    aes_key = os.urandom(32)  # 256 bit key
    iv = os.urandom(16)  # 16 byte IV
    
    # Encrypt password with AES
    password = 'testpass123'
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Pad password to 16 byte boundary
    padding_length = 16 - (len(password) % 16)
    padded_password = password + chr(padding_length) * padding_length
    
    encrypted_password = encryptor.update(padded_password.encode()) + encryptor.finalize()
    encrypted_password_b64 = base64.b64encode(encrypted_password).decode()
    
    # Encrypt AES key with RSA
    encrypted_aes_key = public_key.encrypt(
        aes_key.hex().encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key).decode()
    
    # Create payload
    payload = {
        'data': {
            'email': 'testuser2@example.com',
            'password': {
                'data': encrypted_password_b64,
                'encrypted': True
            }
        },
        'key': encrypted_aes_key_b64,
        'iv': iv.hex()
    }
    
    # Send login request
    response = requests.post('http://localhost:8000/api/login/', json=payload)
    print('Encrypted login response:', response.json())

if __name__ == '__main__':
    test_encrypted_login() 