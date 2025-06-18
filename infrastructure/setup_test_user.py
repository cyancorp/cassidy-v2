#!/usr/bin/env python3
"""
Setup test user for Cassidy API
Creates the default test user if it doesn't exist
"""

import urllib.request
import urllib.error
import json
import sys

def setup_test_user(api_url, username="user_123", password="1234"):
    """Create test user via API"""
    
    # Remove trailing slash if present
    api_url = api_url.rstrip('/')
    
    print(f"Setting up test user '{username}' at {api_url}")
    
    # First try to login to see if user exists
    login_url = f"{api_url}/api/v1/auth/login"
    login_data = json.dumps({
        "username": username,
        "password": password
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(
            login_url,
            data=login_data,
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req)
        print(f"✅ User '{username}' already exists and can login")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(f"User '{username}' not found or wrong password, creating...")
        else:
            print(f"Login error: {e.code} - {e.read().decode()}")
    
    # Create user
    register_url = f"{api_url}/api/v1/auth/register"
    register_data = json.dumps({
        "username": username,
        "password": password,
        "email": f"{username}@example.com",
        "full_name": "Test User"
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(
            register_url,
            data=register_data,
            headers={'Content-Type': 'application/json'}
        )
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode())
        print(f"✅ Created user '{username}' with ID: {result.get('user_id')}")
        return True
    except urllib.error.HTTPError as e:
        error_detail = e.read().decode()
        if "already exists" in error_detail.lower():
            print(f"✅ User '{username}' already exists")
            return True
        else:
            print(f"❌ Failed to create user: {e.code} - {error_detail}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    # Get API URL from command line or use default
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    else:
        # Try to get from environment or use a default
        api_url = "https://tq68ditf6b.execute-api.us-east-1.amazonaws.com/prod"
    
    # Optional: custom username/password
    username = sys.argv[2] if len(sys.argv) > 2 else "user_123"
    password = sys.argv[3] if len(sys.argv) > 3 else "1234"
    
    success = setup_test_user(api_url, username, password)
    sys.exit(0 if success else 1)