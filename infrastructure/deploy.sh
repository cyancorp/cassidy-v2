#!/bin/bash
# Deploy script for Cassidy Lambda stack

echo "Deploying Cassidy Lambda Stack..."
echo "================================"

# Check if we're in the infrastructure directory
if [ ! -f "app.py" ]; then
    echo "Error: Must run from infrastructure directory"
    exit 1
fi

# Deploy the stack
echo "Running CDK deploy..."
cdk deploy --require-approval never

# Get the Lambda function name from the stack output
LAMBDA_NAME=$(aws cloudformation describe-stacks \
    --stack-name CassidyLambdaStack \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
    --output text)

if [ -z "$LAMBDA_NAME" ]; then
    echo "Error: Could not find Lambda function name"
    exit 1
fi

echo ""
echo "Lambda function deployed: $LAMBDA_NAME"
echo ""
echo "Testing Lambda function..."
echo "=========================="

# Test the health endpoint
API_URL=$(aws cloudformation describe-stacks \
    --stack-name CassidyLambdaStack \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text)

echo "API URL: $API_URL"
echo ""
echo "Testing /health endpoint..."
curl -s "$API_URL/health" | jq .

echo ""
echo "Checking Lambda logs..."
echo "======================="
aws logs tail "/aws/lambda/$LAMBDA_NAME" --follow --since 5m