#!/usr/bin/env python3
"""
Startup script for the ESP32 Sensor Dashboard.
This script properly configures and starts the Daphne ASGI server.
"""

import os
import sys
import subprocess
import django
from django.core.management import execute_from_command_line

def check_dependencies():
    """Check if all required dependencies are installed"""
    try:
        import daphne
        import channels
        import rest_framework
        import django_filters
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def check_database():
    """Check if database migrations are up to date"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edgesync.settings')
    django.setup()
    
    try:
        from django.core.management import call_command
        from io import StringIO
        
        # Capture output to check if migrations are needed
        out = StringIO()
        call_command('showmigrations', '--plan', stdout=out)
        output = out.getvalue()
        
        if '[ ]' in output:
            print("⚠️  Unapplied migrations detected. Running migrations...")
            call_command('migrate')
            print("✅ Database migrations completed")
        else:
            print("✅ Database is up to date")
        return True
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False

def start_server(port=8000):
    """Start the Daphne ASGI server"""
    print(f"🚀 Starting Daphne server on port {port}...")
    print("📡 WebSocket endpoint: ws://localhost:8000/ws/sensors/")
    print("🌐 Dashboard: http://localhost:8000/")
    print("⏹️  Press Ctrl+C to stop the server\n")
    
    try:
        # Set environment variable
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edgesync.settings')
        
        # Start Daphne
        subprocess.run([
            'daphne', 
            '-p', str(port), 
            'edgesync.asgi:application'
        ])
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except FileNotFoundError:
        print("❌ Daphne not found. Please install it: pip install daphne")
    except Exception as e:
        print(f"❌ Error starting server: {e}")

def main():
    """Main function"""
    print("=" * 60)
    print("🔧 ESP32 Sensor Dashboard - Server Startup")
    print("=" * 60)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check database
    if not check_database():
        sys.exit(1)
    
    # Parse command line arguments
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("❌ Invalid port number")
            sys.exit(1)
    
    # Start server
    start_server(port)

if __name__ == "__main__":
    main() 