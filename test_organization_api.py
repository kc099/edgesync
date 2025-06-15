#!/usr/bin/env python3
"""
Test script for Organization and Dashboard Template APIs
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000/api"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpass123"

class APITester:
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        
    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def test_login(self):
        """Test user login to get access token"""
        self.log("Testing login...")
        
        # First get public key
        try:
            response = self.session.get(f"{BASE_URL}/public-key/")
            if response.status_code != 200:
                self.log(f"❌ Failed to get public key: {response.status_code}")
                return False
                
            public_key = response.json().get('public_key')
            if not public_key:
                self.log("❌ No public key in response")
                return False
                
            self.log("✅ Got public key successfully")
            
            # For testing, we'll use plain login (in production, this should be encrypted)
            # Note: The backend now requires encrypted data, so this test will show the security requirement
            login_data = {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            }
            
            response = self.session.post(f"{BASE_URL}/login/", json=login_data)
            
            if response.status_code == 400:
                error_msg = response.json().get('error', 'Unknown error')
                if 'Encrypted authentication required' in str(error_msg):
                    self.log("✅ Backend correctly requires encrypted authentication")
                    self.log("ℹ️  For testing purposes, we'll create a test user directly")
                    return self.create_test_user()
                else:
                    self.log(f"❌ Login failed: {error_msg}")
                    return False
            else:
                self.log(f"❌ Unexpected response: {response.status_code}")
                return False
                
        except Exception as e:
            self.log(f"❌ Login error: {e}")
            return False
    
    def create_test_user(self):
        """Create a test user directly in the database for testing"""
        self.log("Creating test user for API testing...")
        
        try:
            # Import Django models
            import os
            import django
            
            # Setup Django
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edgesync.settings')
            django.setup()
            
            from django.contrib.auth.models import User
            from user.models import UserProfile
            from rest_framework_simplejwt.tokens import RefreshToken
            
            # Create or get test user
            user, created = User.objects.get_or_create(
                email=TEST_EMAIL,
                defaults={
                    'username': 'testuser',
                    'first_name': 'Test',
                    'last_name': 'User'
                }
            )
            
            if created:
                user.set_password(TEST_PASSWORD)
                user.save()
                self.log("✅ Created test user")
            else:
                self.log("✅ Using existing test user")
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            self.access_token = str(refresh.access_token)
            self.refresh_token = str(refresh)
            self.user_id = user.id
            
            # Set authorization header
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            
            self.log("✅ Got access token for testing")
            return True
            
        except Exception as e:
            self.log(f"❌ Failed to create test user: {e}")
            return False
    
    def test_organizations(self):
        """Test organization CRUD operations"""
        self.log("\n=== Testing Organizations ===")
        
        # Test GET organizations (should be empty initially)
        response = self.session.get(f"{BASE_URL}/organizations/")
        if response.status_code == 200:
            orgs = response.json().get('organizations', [])
            self.log(f"✅ GET organizations: {len(orgs)} organizations found")
        else:
            self.log(f"❌ GET organizations failed: {response.status_code}")
            return False
        
        # Test CREATE organization
        org_data = {
            "name": "Test Organization",
            "description": "A test organization for API testing",
            "slug": "test-org"
        }
        
        response = self.session.post(f"{BASE_URL}/organizations/", json=org_data)
        if response.status_code == 201:
            org = response.json().get('organization')
            org_id = org['id']
            self.log(f"✅ CREATE organization: Created org with ID {org_id}")
        else:
            self.log(f"❌ CREATE organization failed: {response.status_code}")
            self.log(f"Response: {response.text}")
            return False
        
        # Test GET specific organization
        response = self.session.get(f"{BASE_URL}/organizations/{org_id}/")
        if response.status_code == 200:
            self.log("✅ GET specific organization: Success")
        else:
            self.log(f"❌ GET specific organization failed: {response.status_code}")
        
        # Test UPDATE organization
        update_data = {
            "description": "Updated test organization description"
        }
        
        response = self.session.put(f"{BASE_URL}/organizations/{org_id}/", json=update_data)
        if response.status_code == 200:
            self.log("✅ UPDATE organization: Success")
        else:
            self.log(f"❌ UPDATE organization failed: {response.status_code}")
        
        return org_id
    
    def test_dashboard_templates(self, org_id):
        """Test dashboard template CRUD operations"""
        self.log("\n=== Testing Dashboard Templates ===")
        
        # Test GET templates (should be empty initially)
        response = self.session.get(f"{BASE_URL}/dashboard-templates/")
        if response.status_code == 200:
            templates = response.json().get('templates', [])
            self.log(f"✅ GET templates: {len(templates)} templates found")
        else:
            self.log(f"❌ GET templates failed: {response.status_code}")
            return False
        
        # Test CREATE template
        template_data = {
            "name": "Test Dashboard Template",
            "description": "A test dashboard template",
            "organization_id": org_id,
            "update_frequency": 30,
            "connection_timeout": 10,
            "widgets": [
                {
                    "type": "time_series",
                    "title": "Temperature Over Time",
                    "query": "SELECT timestamp, value FROM sensor_data WHERE sensor_type='temperature'",
                    "datasource": "mysql"
                }
            ],
            "datasources": [
                {
                    "type": "mysql",
                    "name": "Main Database",
                    "connection_string": "mysql://localhost:3306/edgesync"
                }
            ],
            "layout": {
                "rows": [
                    {"panels": [{"id": 1, "span": 12}]}
                ]
            }
        }
        
        response = self.session.post(f"{BASE_URL}/dashboard-templates/", json=template_data)
        if response.status_code == 201:
            template = response.json().get('template')
            template_id = template['id']
            self.log(f"✅ CREATE template: Created template with ID {template_id}")
        else:
            self.log(f"❌ CREATE template failed: {response.status_code}")
            self.log(f"Response: {response.text}")
            return False
        
        # Test GET specific template
        response = self.session.get(f"{BASE_URL}/dashboard-templates/{template_id}/")
        if response.status_code == 200:
            self.log("✅ GET specific template: Success")
        else:
            self.log(f"❌ GET specific template failed: {response.status_code}")
        
        # Test UPDATE template
        update_data = {
            "description": "Updated test dashboard template",
            "update_frequency": 60
        }
        
        response = self.session.put(f"{BASE_URL}/dashboard-templates/{template_id}/", json=update_data)
        if response.status_code == 200:
            self.log("✅ UPDATE template: Success")
        else:
            self.log(f"❌ UPDATE template failed: {response.status_code}")
        
        return template_id
    
    def test_cleanup(self, org_id, template_id):
        """Clean up test data"""
        self.log("\n=== Cleaning Up ===")
        
        # Delete template
        response = self.session.delete(f"{BASE_URL}/dashboard-templates/{template_id}/")
        if response.status_code == 200:
            self.log("✅ DELETE template: Success")
        else:
            self.log(f"❌ DELETE template failed: {response.status_code}")
        
        # Delete organization
        response = self.session.delete(f"{BASE_URL}/organizations/{org_id}/")
        if response.status_code == 200:
            self.log("✅ DELETE organization: Success")
        else:
            self.log(f"❌ DELETE organization failed: {response.status_code}")
    
    def run_tests(self):
        """Run all tests"""
        self.log("🚀 Starting Organization & Dashboard Template API Tests")
        
        # Test login
        if not self.test_login():
            self.log("❌ Login test failed, aborting")
            return False
        
        # Test organizations
        org_id = self.test_organizations()
        if not org_id:
            self.log("❌ Organization tests failed, aborting")
            return False
        
        # Test dashboard templates
        template_id = self.test_dashboard_templates(org_id)
        if not template_id:
            self.log("❌ Dashboard template tests failed")
            return False
        
        # Cleanup
        self.test_cleanup(org_id, template_id)
        
        self.log("\n🎉 All tests completed successfully!")
        return True

if __name__ == "__main__":
    tester = APITester()
    success = tester.run_tests()
    sys.exit(0 if success else 1) 