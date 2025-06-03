#!/usr/bin/env python
"""
Setup script for Google OAuth application in Django Allauth
Run this after adding your GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env
"""

import os
import sys
import django
from pathlib import Path

# Add the project root directory to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edgesync.settings')
django.setup()

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_google_oauth():
    """Set up Google OAuth application"""
    
    # Get credentials from environment
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("❌ Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in your .env file")
        print("Please add these lines to your .env file:")
        print("GOOGLE_CLIENT_ID=your_google_client_id_here")
        print("GOOGLE_CLIENT_SECRET=your_google_client_secret_here")
        return False
    
    try:
        # Get or create the site
        site, created = Site.objects.get_or_create(
            pk=1,
            defaults={
                'domain': '127.0.0.1:8000',
                'name': 'EdgeSync Development'
            }
        )
        
        if created:
            print(f"✅ Created site: {site.domain}")
        else:
            print(f"✅ Site already exists: {site.domain}")
        
        # Create or update Google OAuth app
        google_app, created = SocialApp.objects.update_or_create(
            provider='google',
            defaults={
                'name': 'Google OAuth',
                'client_id': client_id,
                'secret': client_secret,
            }
        )
        
        # Add the site to the app
        google_app.sites.add(site)
        
        if created:
            print("✅ Created Google OAuth application")
        else:
            print("✅ Updated Google OAuth application")
            
        print(f"   Client ID: {client_id[:20]}...")
        print(f"   Redirect URI: http://127.0.0.1:8000/accounts/google/login/callback/")
        print()
        print("🚀 Google OAuth setup completed successfully!")
        print("You can now test login/signup with Google at:")
        print("   http://127.0.0.1:8000/accounts/login/")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up Google OAuth: {e}")
        return False

if __name__ == '__main__':
    print("🔧 Setting up Google OAuth for EdgeSync...")
    print()
    
    success = setup_google_oauth()
    
    if success:
        print()
        print("📝 Next steps:")
        print("1. Make sure your Google Cloud Console has the redirect URI configured:")
        print("   http://127.0.0.1:8000/accounts/google/login/callback/")
        print("2. Run: python manage.py runserver")
        print("3. Visit: http://127.0.0.1:8000/accounts/login/")
    else:
        sys.exit(1) 