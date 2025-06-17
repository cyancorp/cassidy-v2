#!/usr/bin/env python3
"""
Cassidy API Integration Test Suite (Simplified - No Dependencies)

This script tests all major API endpoints using only Python standard library.
Run this after each deployment to catch regressions early.

Usage:
    python3 test_api_simple.py [API_URL] [USERNAME] [PASSWORD]
"""

import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

class APITester:
    def __init__(self, api_url: str, username: str, password: str):
        self.api_url = api_url.rstrip('/')
        self.username = username
        self.password = password
        self.access_token = None
        self.session_id = None
        self.passed_tests = 0
        self.failed_tests = 0
        
    def print_test(self, message: str):
        print(f"\n{YELLOW}[TEST]{NC} {message}")
        
    def print_success(self, message: str):
        print(f"{GREEN}[PASS]{NC} {message}")
        self.passed_tests += 1
        
    def print_error(self, message: str):
        print(f"{RED}[FAIL]{NC} {message}")
        self.failed_tests += 1
        
    def print_info(self, message: str):
        print(f"{BLUE}[INFO]{NC} {message}")
        
    def make_request(self, method: str, endpoint: str, 
                    expected_status: int = 200,
                    data: dict = None, 
                    headers: dict = None,
                    description: str = ""):
        """Make HTTP request and validate response"""
        url = f"{self.api_url}{endpoint}"
        
        if headers is None:
            headers = {}
        if self.access_token and 'Authorization' not in headers:
            headers['Authorization'] = f'Bearer {self.access_token}'
            
        self.print_test(description or f"{method} {endpoint}")
        
        try:
            start_time = time.time()
            
            # Prepare request
            if data:
                data_bytes = json.dumps(data).encode('utf-8')
                headers['Content-Type'] = 'application/json'
                headers['Content-Length'] = str(len(data_bytes))
            else:
                data_bytes = None
                
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
            
            try:
                with urllib.request.urlopen(req) as response:
                    response_data = response.read().decode('utf-8')
                    status_code = response.getcode()
                    elapsed_time = (time.time() - start_time) * 1000
                    
                    if status_code == expected_status:
                        self.print_success(f"Status: {status_code} (took {elapsed_time:.0f}ms)")
                        
                        # Try to parse JSON
                        try:
                            json_response = json.loads(response_data)
                            print(f"Response: {json.dumps(json_response, indent=2)[:200]}...")
                            return True, json_response
                        except:
                            if response_data:
                                print(f"Response: {response_data[:200]}...")
                            return True, response_data
                    else:
                        self.print_error(f"Expected status {expected_status}, got {status_code}")
                        print(f"Response: {response_data[:200]}...")
                        return False, response_data
                        
            except urllib.error.HTTPError as e:
                status_code = e.getcode()
                response_data = e.read().decode('utf-8') if e.fp else ""
                
                if status_code == expected_status:
                    self.print_success(f"Status: {status_code} (expected error)")
                    try:
                        json_response = json.loads(response_data)
                        return True, json_response
                    except:
                        return True, response_data
                else:
                    self.print_error(f"Expected status {expected_status}, got {status_code}")
                    print(f"Response: {response_data[:200]}...")
                    return False, response_data
                    
        except Exception as e:
            self.print_error(f"Request failed: {str(e)}")
            return False, None
            
    def test_root_endpoint(self):
        """Test 1: Root endpoint"""
        success, response = self.make_request(
            "GET", "/", 
            description="Root endpoint should return welcome message"
        )
        if success and isinstance(response, dict):
            if "Welcome to Cassidy AI Journaling Assistant" in response.get("message", ""):
                self.print_success("Welcome message verified")
            else:
                self.print_error("Welcome message not found")
                
    def test_health_endpoint(self):
        """Test 2: Health check"""
        success, response = self.make_request(
            "GET", "/health",
            description="Health check endpoint"
        )
        if success and isinstance(response, dict):
            if response.get("status") == "healthy":
                self.print_success("Service is healthy")
            else:
                self.print_error("Service not healthy")
                
    def test_authentication(self):
        """Test authentication flow"""
        # Test valid login
        success, response = self.make_request(
            "POST", "/api/v1/auth/login",
            data={"username": self.username, "password": self.password},
            description="Login with valid credentials"
        )
        
        if success and isinstance(response, dict):
            self.access_token = response.get("access_token")
            if self.access_token:
                self.print_success(f"Access token received: {self.access_token[:20]}...")
                self.print_info(f"User ID: {response.get('user_id')}")
                return True
            else:
                self.print_error("No access token in response")
        
        return False
        
    def test_chat_session(self):
        """Test chat session and agent interaction"""
        if not self.access_token:
            self.print_error("No access token available, skipping chat tests")
            return
            
        # Create session
        success, response = self.make_request(
            "POST", "/api/v1/sessions",
            data={"conversation_type": "journaling", "metadata": {}},
            description="Create new chat session"
        )
        
        if success and isinstance(response, dict):
            self.session_id = response.get("session_id")
            if self.session_id:
                self.print_success(f"Session created: {self.session_id}")
            else:
                self.print_error("No session ID in response")
                return
        else:
            return
            
        # Send message to agent (simplified test)
        self.print_info("Sending message to agent...")
        success, response = self.make_request(
            "POST", f"/api/v1/agent/chat/{self.session_id}",
            data={"text": "Hi, this is a test message."},
            description="Send message to agent"
        )
        
        if success and isinstance(response, dict):
            agent_text = response.get("text", "")
            if agent_text:
                self.print_success("Agent responded successfully")
                self.print_info(f"Agent said: {agent_text[:100]}...")
            else:
                self.print_error("Agent response missing text")
                
    def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 50)
        print("Cassidy API Integration Test Suite")
        print(f"Testing API at: {self.api_url}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        # Run core tests
        self.test_root_endpoint()
        self.test_health_endpoint()
        
        if self.test_authentication():
            self.test_chat_session()
        
        # Print summary
        print("\n" + "=" * 50)
        print("Test Summary")
        print("=" * 50)
        print(f"{GREEN}Passed: {self.passed_tests}{NC}")
        print(f"{RED}Failed: {self.failed_tests}{NC}")
        print()
        
        if self.failed_tests == 0:
            print(f"{GREEN}All tests passed! ✅{NC}")
            return 0
        else:
            print(f"{RED}Some tests failed! ❌{NC}")
            return 1


def main():
    # Default values
    api_url = "https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod"
    username = "user_123"
    password = "1234"
    
    # Override with command line arguments
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    if len(sys.argv) > 2:
        username = sys.argv[2] 
    if len(sys.argv) > 3:
        password = sys.argv[3]
    
    tester = APITester(api_url, username, password)
    return tester.run_all_tests()


if __name__ == "__main__":
    sys.exit(main())