#!/bin/bash

API_URL="https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod"

echo "🧪 Testing Fixed Cassidy API at: $API_URL"
echo "=================================================="

echo
echo "1. Testing health endpoint..."
curl -s "$API_URL/health" | jq . || echo "Health check failed"

echo
echo "2. Testing user registration..."
REGISTER_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -H "Origin: http://cassidy-frontend-1748872354.s3-website-us-east-1.amazonaws.com" \
  -d '{"username": "test@example.com", "password": "test123", "name": "Test User"}')

echo "$REGISTER_RESPONSE" | jq . || echo "$REGISTER_RESPONSE"

echo
echo "3. Testing user login..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "Origin: http://cassidy-frontend-1748872354.s3-website-us-east-1.amazonaws.com" \
  -d '{"username": "test@example.com", "password": "test123"}')

echo "$LOGIN_RESPONSE" | jq . || echo "$LOGIN_RESPONSE"

# Extract JWT token for further tests
JWT_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token // empty')

if [ -n "$JWT_TOKEN" ]; then
    echo
    echo "4. Testing session creation..."
    SESSION_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/sessions" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $JWT_TOKEN" \
      -d '{"conversation_type": "journaling"}')
    
    echo "$SESSION_RESPONSE" | jq . || echo "$SESSION_RESPONSE"
    
    SESSION_ID=$(echo "$SESSION_RESPONSE" | jq -r '.session_id // empty')
    
    if [ -n "$SESSION_ID" ]; then
        echo
        echo "5. 🚀 Testing AGENT RESPONSE (the critical fix!)..."
        echo "   This should respond in ~2-3 seconds instead of timing out!"
        
        START_TIME=$(date +%s%N)
        AGENT_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/agent/chat/$SESSION_ID" \
          -H "Content-Type: application/json" \
          -H "Authorization: Bearer $JWT_TOKEN" \
          -d '{"text": "Hi! How are you?"}' \
          -w "\nHTTP_STATUS:%{http_code}\nTOTAL_TIME:%{time_total}")
        END_TIME=$(date +%s%N)
        
        DURATION=$(echo "scale=3; ($END_TIME - $START_TIME) / 1000000000" | bc)
        
        echo "Response time: ${DURATION}s"
        echo "$AGENT_RESPONSE" | head -n -2 | jq . || echo "$AGENT_RESPONSE" | head -n -2
        
        HTTP_STATUS=$(echo "$AGENT_RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
        TOTAL_TIME=$(echo "$AGENT_RESPONSE" | grep "TOTAL_TIME:" | cut -d: -f2)
        
        echo "HTTP Status: $HTTP_STATUS"
        echo "Total Time: ${TOTAL_TIME}s"
        
        if [ "$HTTP_STATUS" = "200" ] && [ "$(echo "$TOTAL_TIME < 10" | bc)" = "1" ]; then
            echo "✅ SUCCESS: Agent responded quickly!"
        else
            echo "❌ FAILED: Agent timeout or error"
        fi
    else
        echo "❌ Session creation failed"
    fi
else
    echo "❌ Login failed - cannot test agent"
fi

echo
echo "🏁 Test complete!"