#!/bin/bash

# Deployment script for fresh Cassidy Lambda stack
# Run this from the infrastructure directory

echo "🔥 Tearing down old problematic stack..."
cdk destroy CassidyLambdaStack --force

echo "✅ Deploying new fixed stack with proper VPC networking..."
cdk deploy CassidyLambdaStackFixed --require-approval never

echo "🎉 Deployment complete! Testing the new API..."

# Get the new API URL from CDK outputs
API_URL=$(aws cloudformation describe-stacks --stack-name CassidyLambdaStackFixed --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text)

echo "📡 New API URL: $API_URL"

# Test login
echo "🧪 Testing login..."
curl -X POST "$API_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -H "Origin: http://cassidy-frontend-1748872354.s3-website-us-east-1.amazonaws.com" \
  -d '{"username": "cyan@test.com", "password": "cyppass123"}' \
  -w "\nStatus: %{http_code}\nTime: %{time_total}s\n"

echo "✅ If login succeeded, the agent should now respond quickly to messages!"
echo "🏁 Frontend should connect to: $API_URL"