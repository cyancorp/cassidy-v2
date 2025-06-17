#!/bin/bash
# Check Lambda function status and configuration

echo "Checking Cassidy Lambda Status..."
echo "================================="

# Get the Lambda function name from the stack
LAMBDA_NAME=$(aws cloudformation describe-stacks \
    --stack-name CassidyLambdaStack \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
    --output text 2>/dev/null)

if [ -z "$LAMBDA_NAME" ]; then
    echo "Error: Could not find Lambda function. Is the stack deployed?"
    exit 1
fi

echo "Lambda Function: $LAMBDA_NAME"
echo ""

# Get Lambda configuration
echo "Lambda Configuration:"
echo "===================="
aws lambda get-function-configuration --function-name "$LAMBDA_NAME" \
    --query '{Environment: Environment.Variables, VpcConfig: VpcConfig, Runtime: Runtime, MemorySize: MemorySize, Timeout: Timeout}' \
    --output json | jq .

echo ""
echo "Recent Lambda Logs:"
echo "==================="
aws logs tail "/aws/lambda/$LAMBDA_NAME" --since 30m --max-items 50

echo ""
echo "RDS Database Status:"
echo "===================="
# Get RDS endpoint from stack outputs
DB_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name CassidyLambdaStack \
    --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
    --output text 2>/dev/null)

if [ -n "$DB_ENDPOINT" ]; then
    DB_INSTANCE_ID=$(echo $DB_ENDPOINT | cut -d'.' -f1)
    echo "Database Instance: $DB_INSTANCE_ID"
    
    # Get RDS instance status
    aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_ID" \
        --query 'DBInstances[0].{Status: DBInstanceStatus, Engine: Engine, EngineVersion: EngineVersion, Endpoint: Endpoint.Address, Port: Endpoint.Port}' \
        --output json | jq .
    
    # Check parameter group
    echo ""
    echo "Database Parameter Group:"
    aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_ID" \
        --query 'DBInstances[0].DBParameterGroups[0]' \
        --output json | jq .
fi

echo ""
echo "Security Groups:"
echo "================"
# Get Lambda security group
LAMBDA_SG=$(aws lambda get-function-configuration --function-name "$LAMBDA_NAME" \
    --query 'VpcConfig.SecurityGroupIds[0]' --output text)

if [ -n "$LAMBDA_SG" ] && [ "$LAMBDA_SG" != "None" ]; then
    echo "Lambda Security Group: $LAMBDA_SG"
    aws ec2 describe-security-groups --group-ids "$LAMBDA_SG" \
        --query 'SecurityGroups[0].{GroupName: GroupName, Rules: IpPermissionsEgress[?ToPort != `null`]}' \
        --output json | jq .
fi