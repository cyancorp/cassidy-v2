#!/usr/bin/env python3
"""
Cassidy API Integration Test Suite

This script tests all major API endpoints to ensure the deployment is working correctly.
Run this after each deployment to catch regressions early.

Usage:
    python test_api.py [--api-url URL] [--username USER] [--password PASS]
    
Environment variables:
    API_URL: Override default API URL
    TEST_USERNAME: Override default test username
    TEST_PASSWORD: Override default test password
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, Any, Optional, Tuple
import requests
from requests.exceptions import RequestException
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
        self.test_results = []
        
    def print_test(self, message: str):
        """Print test header"""
        print(f"\n{YELLOW}[TEST]{NC} {message}")
        
    def print_success(self, message: str):
        """Print success message"""
        print(f"{GREEN}[PASS]{NC} {message}")
        self.passed_tests += 1
        
    def print_error(self, message: str):
        """Print error message"""
        print(f"{RED}[FAIL]{NC} {message}")
        self.failed_tests += 1
        
    def print_info(self, message: str):
        """Print info message"""
        print(f"{BLUE}[INFO]{NC} {message}")
        
    def make_request(self, method: str, endpoint: str, 
                    expected_status: int = 200,
                    data: Optional[Dict] = None, 
                    headers: Optional[Dict] = None,
                    description: str = "") -> Tuple[bool, Any]:
        """Make HTTP request and validate response"""
        url = f"{self.api_url}{endpoint}"
        
        # Add auth header if we have a token
        if headers is None:
            headers = {}
        if self.access_token and 'Authorization' not in headers:
            headers['Authorization'] = f'Bearer {self.access_token}'
            
        self.print_test(description or f"{method} {endpoint}")
        
        try:
            start_time = time.time()
            
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers)
            elif method == "OPTIONS":
                response = requests.options(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            elapsed_time = (time.time() - start_time) * 1000  # ms
            
            # Check status code
            if response.status_code == expected_status:
                self.print_success(f"Status: {response.status_code} (took {elapsed_time:.0f}ms)")
                
                # Try to parse JSON response
                try:
                    json_response = response.json()
                    print(f"Response: {json.dumps(json_response, indent=2)[:200]}...")
                    return True, json_response
                except:
                    # Not JSON response
                    if response.text:
                        print(f"Response: {response.text[:200]}...")
                    return True, response.text
            else:
                self.print_error(f"Expected status {expected_status}, got {response.status_code}")
                print(f"Response: {response.text[:200]}...")
                return False, response.text
                
        except RequestException as e:
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
                
    def test_docs_endpoint(self):
        """Test 3: API documentation"""
        success, response = self.make_request(
            "GET", "/docs",
            description="API documentation endpoint"
        )
        if success and isinstance(response, str) and "<title>" in response:
            self.print_success("Swagger documentation accessible")
            
    def test_authentication(self):
        """Test 4-5: Authentication flow"""
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
            else:
                self.print_error("No access token in response")
                return False
        else:
            return False
            
        # Test invalid login
        success, response = self.make_request(
            "POST", "/api/v1/auth/login",
            expected_status=401,
            data={"username": "invalid", "password": "wrong"},
            description="Login with invalid credentials should fail"
        )
        
        return True
        
    def test_authenticated_endpoints(self):
        """Test 6-7: Authenticated user endpoints"""
        if not self.access_token:
            self.print_error("No access token available, skipping authenticated tests")
            return
            
        # Get user profile
        success, response = self.make_request(
            "GET", "/api/v1/auth/me",
            description="Get current user profile"
        )
        
        # Get user preferences
        success, response = self.make_request(
            "GET", "/api/v1/user/preferences",
            description="Get user preferences"
        )
        
    def test_chat_session(self):
        """Test 8-10: Chat session and agent interaction"""
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
            
        # Send message to agent
        self.print_info("Sending message to agent (this may take a few seconds)...")
        success, response = self.make_request(
            "POST", f"/api/v1/agent/chat/{self.session_id}",
            data={"text": "Hi, this is a test message. How are you today?"},
            description="Send message to agent"
        )
        
        if success and isinstance(response, dict):
            agent_text = response.get("text", "")
            if agent_text:
                self.print_success("Agent responded successfully")
                self.print_info(f"Agent said: {agent_text[:100]}...")
            else:
                self.print_error("Agent response missing text")
                
        # Get session messages
        success, response = self.make_request(
            "GET", f"/api/v1/sessions/{self.session_id}/messages",
            description="Get session messages"
        )
        
        if success and isinstance(response, list):
            self.print_info(f"Found {len(response)} messages in session")
            
    def test_cors(self):
        """Test 11: CORS preflight"""
        headers = {
            "Origin": "https://donx85isqomd0.cloudfront.net",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Authorization"
        }
        
        success, response = self.make_request(
            "OPTIONS", "/api/v1/auth/login",
            expected_status=200,  # Some APIs return 204
            headers=headers,
            description="CORS preflight request"
        )
        
    def test_rate_limiting(self):
        """Test 12: Rate limiting check"""
        self.print_test("Testing multiple rapid requests")
        
        results = []
        for i in range(5):
            try:
                start = time.time()
                response = requests.get(f"{self.api_url}/health")
                elapsed = (time.time() - start) * 1000
                results.append((response.status_code, elapsed))
                print(f"  Request {i+1}: {response.status_code} ({elapsed:.0f}ms)")
            except:
                results.append((0, 0))
                print(f"  Request {i+1}: Failed")
                
        # Check if any were rate limited
        rate_limited = any(status == 429 for status, _ in results)
        if rate_limited:
            self.print_info("Rate limiting is active")
        else:
            self.print_success("All requests completed without rate limiting")
            
    def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 50)
        print(f"Cassidy API Integration Test Suite")
        print(f"Testing API at: {self.api_url}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        # Run tests in order
        self.test_root_endpoint()
        self.test_health_endpoint()
        self.test_docs_endpoint()
        
        if self.test_authentication():
            self.test_authenticated_endpoints()
            self.test_chat_session()
            
        self.test_cors()
        self.test_rate_limiting()
        
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
    parser = argparse.ArgumentParser(description="Test Cassidy API deployment")
    parser.add_argument("--api-url", 
                       default=os.environ.get("API_URL", "https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod"),
                       help="API base URL")
    parser.add_argument("--username",
                       default=os.environ.get("TEST_USERNAME", "user_123"),
                       help="Test username")
    parser.add_argument("--password",
                       default=os.environ.get("TEST_PASSWORD", "1234"),
                       help="Test password")
    
    args = parser.parse_args()
    
    tester = APITester(args.api_url, args.username, args.password)
    return tester.run_all_tests()


if __name__ == "__main__":
    sys.exit(main())