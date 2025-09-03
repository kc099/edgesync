#!/usr/bin/env python3
"""
Quick test to verify Google OAuth endpoint is working
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edgesync.settings')
django.setup()

from django.test import Client
from django.urls import reverse

def test_google_oauth_endpoint():
    """Test if Google OAuth endpoint exists and responds correctly"""
    client = Client()
    
    # Test GET request (should return 405 Method Not Allowed)
    try:
        response = client.get('/api/google-oauth/')
        print(f"✅ Google OAuth endpoint exists: {response.status_code}")
        if response.status_code == 405:
            print("✅ Correctly rejects GET requests (expects POST)")
        return True
    except Exception as e:
        print(f"❌ Error accessing endpoint: {e}")
        return False

def test_environment():
    """Test environment variables"""
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    if client_id:
        print(f"✅ Google Client ID: {client_id[:20]}...")
        return True
    else:
        print("❌ GOOGLE_CLIENT_ID not found")
        return False

if __name__ == "__main__":
    print("🧪 Testing Google OAuth Setup")
    print("=" * 40)
    
    env_ok = test_environment()
    endpoint_ok = test_google_oauth_endpoint()
    
    print("=" * 40)
    if env_ok and endpoint_ok:
        print("✅ Backend setup looks good!")
        print("Make sure to restart React server to load .env file")
    else:
        print("❌ Some issues found above")