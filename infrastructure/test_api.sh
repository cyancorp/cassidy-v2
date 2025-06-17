#!/bin/bash

# Cassidy API Integration Test Script
# Run this after deployment to verify all endpoints are working correctly

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod}"
TEST_USERNAME="${TEST_USERNAME:-user_123}"
TEST_PASSWORD="${TEST_PASSWORD:-1234}"

# Test results
PASSED_TESTS=0
FAILED_TESTS=0

# Helper functions
print_test() {
    echo -e "\n${YELLOW}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED_TESTS++))
}

print_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED_TESTS++))
}

# Function to test endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local expected_status=$3
    local data=$4
    local headers=$5
    local description=$6
    
    print_test "$description"
    
    # Build curl command
    local curl_cmd="curl -s -w '\n%{http_code}' -X $method '$API_URL$endpoint'"
    
    if [ ! -z "$headers" ]; then
        curl_cmd="$curl_cmd -H '$headers'"
    fi
    
    if [ ! -z "$data" ]; then
        curl_cmd="$curl_cmd -H 'Content-Type: application/json' -d '$data'"
    fi
    
    # Execute curl and capture response
    local response=$(eval $curl_cmd 2>/dev/null || true)
    local status_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')
    
    if [ "$status_code" = "$expected_status" ]; then
        print_success "Status code: $status_code"
        echo "Response: $body"
        echo "$body"  # Return body for further processing
    else
        print_error "Expected status $expected_status, got $status_code"
        echo "Response: $body"
        return 1
    fi
}

# Start testing
echo "========================================="
echo "Cassidy API Integration Test Suite"
echo "Testing API at: $API_URL"
echo "========================================="

# Test 1: Root endpoint
print_test "Testing root endpoint"
response=$(test_endpoint "GET" "/" "200" "" "" "Root endpoint should return welcome message")
if echo "$response" | grep -q "Welcome to Cassidy AI Journaling Assistant"; then
    print_success "Welcome message found"
else
    print_error "Welcome message not found in response"
fi

# Test 2: Health check
response=$(test_endpoint "GET" "/health" "200" "" "" "Health check endpoint")
if echo "$response" | grep -q '"status":"healthy"'; then
    print_success "Health check passed"
else
    print_error "Health check failed"
fi

# Test 3: API documentation
test_endpoint "GET" "/docs" "200" "" "" "API documentation endpoint"

# Test 4: Login with valid credentials
print_test "Testing authentication flow"
login_response=$(test_endpoint "POST" "/api/v1/auth/login" "200" '{"username":"'$TEST_USERNAME'","password":"'$TEST_PASSWORD'"}' "" "Login with valid credentials")

# Extract access token
ACCESS_TOKEN=$(echo "$login_response" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
if [ ! -z "$ACCESS_TOKEN" ]; then
    print_success "Access token received: ${ACCESS_TOKEN:0:20}..."
else
    print_error "Failed to extract access token"
    exit 1
fi

# Test 5: Login with invalid credentials
test_endpoint "POST" "/api/v1/auth/login" "401" '{"username":"invalid","password":"wrong"}' "" "Login with invalid credentials should fail" || true

# Test 6: Get user profile (authenticated)
test_endpoint "GET" "/api/v1/auth/me" "200" "" "Authorization: Bearer $ACCESS_TOKEN" "Get current user profile"

# Test 7: Get user preferences
test_endpoint "GET" "/api/v1/user/preferences" "200" "" "Authorization: Bearer $ACCESS_TOKEN" "Get user preferences"

# Test 8: Create a chat session
print_test "Testing chat session creation"
session_response=$(test_endpoint "POST" "/api/v1/sessions" "200" '{"conversation_type":"journaling","metadata":{}}' "Authorization: Bearer $ACCESS_TOKEN" "Create new chat session")

# Extract session ID
SESSION_ID=$(echo "$session_response" | grep -o '"session_id":"[^"]*' | cut -d'"' -f4)
if [ ! -z "$SESSION_ID" ]; then
    print_success "Session created: $SESSION_ID"
else
    print_error "Failed to extract session ID"
    exit 1
fi

# Test 9: Send message to agent
print_test "Testing agent chat functionality"
chat_response=$(test_endpoint "POST" "/api/v1/agent/chat/$SESSION_ID" "200" '{"text":"Hi, this is a test message"}' "Authorization: Bearer $ACCESS_TOKEN" "Send message to agent")

# Check if agent responded
if echo "$chat_response" | grep -q '"text"'; then
    print_success "Agent responded successfully"
    # Extract and display agent response
    agent_text=$(echo "$chat_response" | grep -o '"text":"[^"]*' | cut -d'"' -f4)
    echo "Agent said: $agent_text"
else
    print_error "Agent did not respond with text"
fi

# Test 10: Get session messages
test_endpoint "GET" "/api/v1/sessions/$SESSION_ID/messages" "200" "" "Authorization: Bearer $ACCESS_TOKEN" "Get session messages"

# Test 11: Test CORS preflight
print_test "Testing CORS preflight request"
cors_response=$(curl -s -X OPTIONS "$API_URL/api/v1/auth/login" \
    -H "Origin: https://donx85isqomd0.cloudfront.net" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: Content-Type,Authorization" \
    -w '\n%{http_code}' 2>/dev/null || true)
    
cors_status=$(echo "$cors_response" | tail -n1)
if [ "$cors_status" = "200" ] || [ "$cors_status" = "204" ]; then
    print_success "CORS preflight passed"
else
    print_error "CORS preflight failed with status $cors_status"
fi

# Test 12: Test rate limiting (optional)
print_test "Testing multiple rapid requests (checking for rate limits)"
for i in {1..5}; do
    response=$(curl -s -w '%{http_code}' -o /dev/null "$API_URL/health")
    if [ "$response" = "200" ]; then
        echo -n "."
    else
        echo -n "X"
    fi
done
echo ""
print_success "Rate limit test completed"

# Summary
echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✅${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed! ❌${NC}"
    exit 1
fi