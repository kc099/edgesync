#!/usr/bin/env python
"""
Encryption Diagnostic Script
Run this on the server to diagnose RSA key issues
Usage: python diagnose_encryption.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, '/var/www/app/edgesync')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edgesync.settings')
django.setup()

from user.utils.encryption import encryption_manager
from cryptography.hazmat.primitives import serialization
import base64

def main():
    print("=" * 60)
    print("ENCRYPTION DIAGNOSTIC TOOL")
    print("=" * 60)
    print()
    
    # 1. Check environment variables
    print("1. Checking Environment Variables:")
    print("-" * 60)
    env_private_file = os.getenv('RSA_PRIVATE_KEY_FILE')
    env_public_file = os.getenv('RSA_PUBLIC_KEY_FILE')
    env_private_pem = os.getenv('RSA_PRIVATE_KEY_PEM')
    env_public_pem = os.getenv('RSA_PUBLIC_KEY_PEM')
    
    print(f"   RSA_PRIVATE_KEY_FILE: {'✓ SET' if env_private_file else '✗ NOT SET'}")
    if env_private_file:
        print(f"      Path: {env_private_file}")
        if os.path.exists(env_private_file):
            print(f"      File exists: ✓")
            print(f"      Readable: {'✓' if os.access(env_private_file, os.R_OK) else '✗ PERMISSION DENIED'}")
        else:
            print(f"      File exists: ✗ FILE NOT FOUND")
    
    print(f"   RSA_PUBLIC_KEY_FILE:  {'✓ SET' if env_public_file else '✗ NOT SET'}")
    if env_public_file:
        print(f"      Path: {env_public_file}")
        if os.path.exists(env_public_file):
            print(f"      File exists: ✓")
            print(f"      Readable: {'✓' if os.access(env_public_file, os.R_OK) else '✗ PERMISSION DENIED'}")
        else:
            print(f"      File exists: ✗ FILE NOT FOUND")
    
    print(f"   RSA_PRIVATE_KEY_PEM:  {'✓ SET' if env_private_pem else '✗ NOT SET'}")
    print(f"   RSA_PUBLIC_KEY_PEM:   {'✓ SET' if env_public_pem else '✗ NOT SET'}")
    print()
    
    # 2. Check loaded keys
    print("2. Checking Loaded Keys:")
    print("-" * 60)
    try:
        public_key_pem = encryption_manager.get_public_key_pem()
        print("   ✓ Public key loaded successfully")
        print()
        print("   Public Key Preview:")
        print("   " + "\n   ".join(public_key_pem.split('\n')[:3]))
        print("   ...")
        print("   " + "\n   ".join(public_key_pem.split('\n')[-2:]))
        print()
        
        # Extract key fingerprint
        from cryptography.hazmat.primitives import hashes
        public_key_bytes = encryption_manager._public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        import hashlib
        fingerprint = hashlib.sha256(public_key_bytes).hexdigest()[:16]
        print(f"   Key Fingerprint: {fingerprint}")
        
    except Exception as e:
        print(f"   ✗ Failed to load public key: {e}")
        return
    print()
    
    # 3. Test encryption/decryption
    print("3. Testing Encryption/Decryption:")
    print("-" * 60)
    try:
        test_data = "test_password_123"
        print(f"   Test plaintext: {test_data}")
        
        # Simulate frontend encryption
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        import secrets
        
        # Generate AES key (like frontend does)
        aes_key_hex = secrets.token_hex(32)  # 256 bits
        print(f"   Generated AES key: {aes_key_hex[:16]}...")
        
        # Encrypt AES key with RSA (like frontend does)
        encrypted_aes_key = encryption_manager._public_key.encrypt(
            aes_key_hex.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key).decode()
        print(f"   Encrypted AES key (base64): {encrypted_aes_key_b64[:40]}...")
        
        # Try to decrypt
        decrypted_aes_key_hex = encryption_manager.decrypt_rsa(encrypted_aes_key_b64)
        
        if decrypted_aes_key_hex == aes_key_hex:
            print("   ✓ RSA encryption/decryption working correctly!")
        else:
            print("   ✗ RSA decryption mismatch!")
            print(f"      Expected: {aes_key_hex}")
            print(f"      Got:      {decrypted_aes_key_hex}")
            
    except Exception as e:
        print(f"   ✗ Encryption test failed: {e}")
        import traceback
        traceback.print_exc()
        return
    print()
    
    # 4. Check if key matches file
    print("4. Verifying Key Consistency:")
    print("-" * 60)
    if env_private_file and os.path.exists(env_private_file):
        try:
            with open(env_private_file, 'rb') as f:
                file_key_bytes = f.read()
            file_public_key = serialization.load_pem_private_key(
                file_key_bytes,
                password=None,
                backend=default_backend()
            ).public_key()
            
            file_public_pem = file_public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode()
            
            if file_public_pem == public_key_pem:
                print("   ✓ Loaded key matches file key")
            else:
                print("   ✗ KEY MISMATCH!")
                print("   The key loaded in memory doesn't match the file.")
                print("   This means encryption_manager is using a different key!")
                print()
                print("   File Key Preview:")
                print("   " + "\n   ".join(file_public_pem.split('\n')[:3]))
                return
        except Exception as e:
            print(f"   ✗ Failed to verify key: {e}")
    else:
        print("   ⚠ No file key to compare (using generated key)")
    print()
    
    # 5. Summary
    print("=" * 60)
    print("DIAGNOSIS SUMMARY")
    print("=" * 60)
    
    if env_private_file and os.path.exists(env_private_file):
        print("✓ Configuration appears correct")
        print()
        print("Next steps:")
        print("1. Restart your Django service:")
        print("   sudo systemctl restart edgesync")
        print()
        print("2. Check logs for encryption errors:")
        print("   sudo journalctl -u edgesync -f | grep -i 'decrypt\\|encrypt\\|rsa'")
        print()
        print("3. Test login/signup from frontend")
    else:
        print("✗ CONFIGURATION ERROR")
        print()
        print("You need to:")
        print("1. Generate RSA keys:")
        print("   sudo mkdir -p /etc/edgesync/keys")
        print("   sudo openssl genrsa -out /etc/edgesync/keys/rsa_private.pem 2048")
        print("   sudo openssl rsa -in /etc/edgesync/keys/rsa_private.pem -pubout -out /etc/edgesync/keys/rsa_public.pem")
        print()
        print("2. Set permissions:")
        print("   sudo chown www-data:www-data /etc/edgesync/keys/*.pem")
        print("   sudo chmod 600 /etc/edgesync/keys/rsa_private.pem")
        print()
        print("3. Add to .env:")
        print("   RSA_PRIVATE_KEY_FILE=/etc/edgesync/keys/rsa_private.pem")
        print("   RSA_PUBLIC_KEY_FILE=/etc/edgesync/keys/rsa_public.pem")
        print()
        print("4. Restart service:")
        print("   sudo systemctl restart edgesync")

if __name__ == '__main__':
    main()
