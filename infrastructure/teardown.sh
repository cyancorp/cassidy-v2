#!/bin/bash

# Comprehensive teardown script for Cassidy infrastructure
# This script removes ALL AWS resources created by the CDK stacks

set -e

echo "🔥 Starting comprehensive teardown of Cassidy infrastructure..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if AWS CLI is configured
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS CLI is not configured or credentials are invalid"
        exit 1
    fi
    
    log_info "AWS CLI is configured"
}

# Function to delete CloudFormation stacks
delete_cloudformation_stacks() {
    log_info "Deleting CloudFormation stacks..."
    
    # Get all Cassidy-related stacks
    STACKS=$(aws cloudformation list-stacks \
        --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE CREATE_FAILED UPDATE_FAILED UPDATE_ROLLBACK_COMPLETE \
        --query "StackSummaries[?contains(StackName, 'Cassidy')].StackName" \
        --output text)
    
    if [ -z "$STACKS" ]; then
        log_warn "No CloudFormation stacks found"
    else
        for stack in $STACKS; do
            log_info "Deleting stack: $stack"
            aws cloudformation delete-stack --stack-name "$stack" || log_warn "Failed to delete stack $stack"
        done
        
        # Wait for all stacks to be deleted
        for stack in $STACKS; do
            log_info "Waiting for stack deletion to complete: $stack"
            aws cloudformation wait stack-delete-complete --stack-name "$stack" 2>/dev/null || log_warn "Stack $stack may have already been deleted"
        done
    fi
}

# Function to delete RDS databases (handles deletion protection)
delete_rds_databases() {
    log_info "Deleting RDS databases..."
    
    # Get all Cassidy-related RDS instances
    DBS=$(aws rds describe-db-instances \
        --query "DBInstances[?contains(DBInstanceIdentifier, 'cassidy')].DBInstanceIdentifier" \
        --output text)
    
    if [ -z "$DBS" ]; then
        log_warn "No RDS databases found"
    else
        for db in $DBS; do
            log_info "Processing database: $db"
            
            # Disable deletion protection first
            log_info "Disabling deletion protection for $db"
            aws rds modify-db-instance \
                --db-instance-identifier "$db" \
                --no-deletion-protection \
                --apply-immediately \
                2>/dev/null || log_warn "Failed to disable deletion protection for $db"
            
            # Wait a moment for the modification to take effect
            sleep 5
            
            # Delete the database (skip final snapshot)
            log_info "Deleting database: $db"
            aws rds delete-db-instance \
                --db-instance-identifier "$db" \
                --skip-final-snapshot \
                2>/dev/null || log_warn "Failed to delete database $db"
        done
        
        # Wait for databases to be deleted
        for db in $DBS; do
            log_info "Waiting for database deletion to complete: $db"
            aws rds wait db-instance-deleted --db-instance-identifier "$db" 2>/dev/null || log_warn "Database $db may have already been deleted"
        done
    fi
}

# Function to delete SSM parameters
delete_ssm_parameters() {
    log_info "Deleting SSM parameters..."
    
    # Get all Cassidy-related parameters
    PARAMS=$(aws ssm get-parameters-by-path \
        --path "/cassidy" \
        --recursive \
        --query "Parameters[].Name" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$PARAMS" ]; then
        log_warn "No SSM parameters found"
    else
        for param in $PARAMS; do
            log_info "Deleting parameter: $param"
            aws ssm delete-parameter --name "$param" || log_warn "Failed to delete parameter $param"
        done
    fi
}

# Function to delete Secrets Manager secrets
delete_secrets() {
    log_info "Deleting Secrets Manager secrets..."
    
    # Get all Cassidy-related secrets
    SECRETS=$(aws secretsmanager list-secrets \
        --query "SecretList[?contains(Name, 'cassidy') || contains(Name, 'Cassidy')].Name" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$SECRETS" ]; then
        log_warn "No Secrets Manager secrets found"
    else
        for secret in $SECRETS; do
            log_info "Deleting secret: $secret"
            aws secretsmanager delete-secret \
                --secret-id "$secret" \
                --force-delete-without-recovery \
                2>/dev/null || log_warn "Failed to delete secret $secret"
        done
    fi
}

# Function to delete Lambda functions
delete_lambda_functions() {
    log_info "Deleting Lambda functions..."
    
    # Get all Cassidy-related Lambda functions
    FUNCTIONS=$(aws lambda list-functions \
        --query "Functions[?contains(FunctionName, 'Cassidy')].FunctionName" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$FUNCTIONS" ]; then
        log_warn "No Lambda functions found"
    else
        for func in $FUNCTIONS; do
            log_info "Deleting Lambda function: $func"
            aws lambda delete-function --function-name "$func" || log_warn "Failed to delete function $func"
        done
    fi
}

# Function to delete S3 buckets and their contents
delete_s3_buckets() {
    log_info "Deleting S3 buckets..."
    
    # Get all Cassidy-related S3 buckets
    BUCKETS=$(aws s3api list-buckets \
        --query "Buckets[?contains(Name, 'cassidy')].Name" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$BUCKETS" ]; then
        log_warn "No S3 buckets found"
    else
        for bucket in $BUCKETS; do
            log_info "Emptying and deleting S3 bucket: $bucket"
            
            # Empty the bucket first
            aws s3 rm "s3://$bucket" --recursive 2>/dev/null || log_warn "Failed to empty bucket $bucket"
            
            # Delete the bucket
            aws s3api delete-bucket --bucket "$bucket" 2>/dev/null || log_warn "Failed to delete bucket $bucket"
        done
    fi
}

# Function to delete API Gateway APIs
delete_api_gateways() {
    log_info "Deleting API Gateway APIs..."
    
    # Get all Cassidy-related REST APIs
    APIS=$(aws apigateway get-rest-apis \
        --query "items[?contains(name, 'cassidy')].id" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$APIS" ]; then
        log_warn "No API Gateway APIs found"
    else
        for api in $APIS; do
            log_info "Deleting API Gateway: $api"
            aws apigateway delete-rest-api --rest-api-id "$api" || log_warn "Failed to delete API $api"
        done
    fi
}

# Function to delete VPCs and related resources
delete_vpcs() {
    log_info "Deleting VPCs and related resources..."
    
    # Get all Cassidy-related VPCs
    VPCS=$(aws ec2 describe-vpcs \
        --query "Vpcs[?Tags[?Key=='Name' && contains(Value, 'cassidy')]].VpcId" \
        --output text 2>/dev/null || echo "")
    
    if [ -z "$VPCS" ]; then
        log_warn "No VPCs found"
    else
        for vpc in $VPCS; do
            log_info "Processing VPC: $vpc"
            
            # Delete security groups (except default)
            SGs=$(aws ec2 describe-security-groups \
                --filters "Name=vpc-id,Values=$vpc" \
                --query "SecurityGroups[?GroupName!='default'].GroupId" \
                --output text 2>/dev/null || echo "")
            
            for sg in $SGs; do
                log_info "Deleting security group: $sg"
                aws ec2 delete-security-group --group-id "$sg" 2>/dev/null || log_warn "Failed to delete security group $sg"
            done
            
            # Delete subnets
            SUBNETS=$(aws ec2 describe-subnets \
                --filters "Name=vpc-id,Values=$vpc" \
                --query "Subnets[].SubnetId" \
                --output text 2>/dev/null || echo "")
            
            for subnet in $SUBNETS; do
                log_info "Deleting subnet: $subnet"
                aws ec2 delete-subnet --subnet-id "$subnet" 2>/dev/null || log_warn "Failed to delete subnet $subnet"
            done
            
            # Delete route tables (except main)
            ROUTE_TABLES=$(aws ec2 describe-route-tables \
                --filters "Name=vpc-id,Values=$vpc" \
                --query "RouteTables[?Associations[0].Main!=\`true\`].RouteTableId" \
                --output text 2>/dev/null || echo "")
            
            for rt in $ROUTE_TABLES; do
                log_info "Deleting route table: $rt"
                aws ec2 delete-route-table --route-table-id "$rt" 2>/dev/null || log_warn "Failed to delete route table $rt"
            done
            
            # Delete internet gateways
            IGWs=$(aws ec2 describe-internet-gateways \
                --filters "Name=attachment.vpc-id,Values=$vpc" \
                --query "InternetGateways[].InternetGatewayId" \
                --output text 2>/dev/null || echo "")
            
            for igw in $IGWs; do
                log_info "Detaching and deleting internet gateway: $igw"
                aws ec2 detach-internet-gateway --internet-gateway-id "$igw" --vpc-id "$vpc" 2>/dev/null || log_warn "Failed to detach IGW $igw"
                aws ec2 delete-internet-gateway --internet-gateway-id "$igw" 2>/dev/null || log_warn "Failed to delete IGW $igw"
            done
            
            # Finally delete the VPC
            log_info "Deleting VPC: $vpc"
            aws ec2 delete-vpc --vpc-id "$vpc" 2>/dev/null || log_warn "Failed to delete VPC $vpc"
        done
    fi
}

# Function to clean up CDK bootstrap resources if they exist
cleanup_cdk_bootstrap() {
    log_info "Checking for CDK bootstrap resources..."
    
    # Check if CDK bootstrap stack exists
    if aws cloudformation describe-stacks --stack-name CDKToolkit &> /dev/null; then
        log_warn "CDK bootstrap stack (CDKToolkit) found - leaving it intact as it may be used by other projects"
    fi
    
    # Clean up any remaining CDK-generated resources
    log_info "Cleaning up temporary CDK assets..."
    
    # Clean up ECR images in CDK repositories but keep the repositories
    REPOS=$(aws ecr describe-repositories \
        --query "repositories[?contains(repositoryName, 'cdk-')].repositoryName" \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$REPOS" ]; then
        for repo in $REPOS; do
            log_info "Cleaning images from ECR repository: $repo"
            # Delete all images but keep the repository
            IMAGES=$(aws ecr list-images --repository-name "$repo" --query 'imageIds[].imageDigest' --output text 2>/dev/null || echo "")
            if [ ! -z "$IMAGES" ]; then
                for image in $IMAGES; do
                    aws ecr batch-delete-image --repository-name "$repo" --image-ids imageDigest="$image" 2>/dev/null || true
                done
            fi
        done
        log_info "CDK ECR repositories cleaned but preserved for future deployments"
    fi
}

# Main execution
main() {
    log_info "Starting comprehensive Cassidy infrastructure teardown"
    
    # Confirm with user
    echo -e "${YELLOW}⚠️  This will DELETE ALL Cassidy-related AWS resources including:${NC}"
    echo "   - CloudFormation stacks"
    echo "   - RDS databases (with deletion protection disabled)"
    echo "   - Lambda functions"
    echo "   - S3 buckets and contents"
    echo "   - API Gateway APIs"
    echo "   - VPCs and networking resources"
    echo "   - SSM parameters"
    echo "   - Secrets Manager secrets"
    echo ""
    read -p "Are you sure? Type 'yes' to continue: " -r
    echo
    if [[ ! $REPLY =~ ^yes$ ]]; then
        log_info "Teardown cancelled"
        exit 0
    fi
    
    check_aws_cli
    
    # Execute teardown in order
    delete_cloudformation_stacks
    delete_rds_databases
    delete_lambda_functions
    delete_s3_buckets
    delete_api_gateways
    delete_ssm_parameters
    delete_secrets
    cleanup_cdk_bootstrap
    delete_vpcs
    
    log_info "✅ Teardown complete!"
    log_info "You can now run a clean deployment with: ./deploy.sh"
}

# Run main function
main "$@"