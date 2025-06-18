#!/bin/bash

# Unified deployment script for Cassidy infrastructure
# Supports deploying frontend, backend, or both stacks

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [COMPONENT]"
    echo ""
    echo "COMPONENT:"
    echo "  backend     Deploy only the backend stack (Lambda + RDS + API Gateway)"
    echo "  frontend    Deploy only the frontend stack (S3 + CloudFront)"
    echo "  both        Deploy both stacks (default if no component specified)"
    echo ""
    echo "OPTIONS:"
    echo "  --check-deps        Check dependencies before deployment"
    echo "  --no-build         Skip frontend build step"
    echo "  --no-test          Skip post-deployment testing"
    echo "  --force            Force deployment without confirmation"
    echo "  --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Deploy both stacks"
    echo "  $0 backend           # Deploy only backend"
    echo "  $0 frontend          # Deploy only frontend"
    echo "  $0 both --no-test    # Deploy both without testing"
    echo "  $0 backend --force   # Force backend deployment"
}

# Function to check dependencies
check_dependencies() {
    log_step "Checking dependencies..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS CLI is not configured or credentials are invalid"
        exit 1
    fi
    
    # Check CDK
    if ! command -v cdk &> /dev/null; then
        log_error "AWS CDK is not installed. Install with: npm install -g aws-cdk"
        exit 1
    fi
    
    # Check if we're in the right directory
    if [ ! -f "app.py" ] || [ ! -f "cdk.json" ]; then
        log_error "Must run from infrastructure directory"
        exit 1
    fi
    
    # Check if CDK dependencies are installed
    if [ ! -d "node_modules" ]; then
        log_info "Installing CDK dependencies..."
        npm install
    fi
    
    log_info "All dependencies are available"
}

# Function to check required AWS parameters
check_aws_parameters() {
    log_step "Checking required AWS SSM parameters..."
    
    # Required parameters
    REQUIRED_PARAMS=(
        "/cassidy/jwt-secret-key"
        "/cassidy/anthropic-api-key"
    )
    
    MISSING_PARAMS=()
    
    for param in "${REQUIRED_PARAMS[@]}"; do
        if ! aws ssm get-parameter --name "$param" --with-decryption &> /dev/null; then
            MISSING_PARAMS+=("$param")
        fi
    done
    
    if [ ${#MISSING_PARAMS[@]} -gt 0 ]; then
        log_error "Missing required AWS SSM parameters:"
        for param in "${MISSING_PARAMS[@]}"; do
            echo "  - $param"
        done
        echo ""
        echo "Create them with:"
        echo "  aws ssm put-parameter --name '/cassidy/jwt-secret-key' --value 'your-jwt-secret' --type 'SecureString'"
        echo "  aws ssm put-parameter --name '/cassidy/anthropic-api-key' --value 'your-anthropic-key' --type 'SecureString'"
        exit 1
    fi
    
    log_info "All required parameters are present"
}

# Function to build frontend
build_frontend() {
    if [ "$SKIP_BUILD" = "true" ]; then
        log_warn "Skipping frontend build (--no-build specified)"
        return
    fi
    
    log_step "Building frontend..."
    
    if [ ! -d "../frontend" ]; then
        log_error "Frontend directory not found"
        exit 1
    fi
    
    cd ../frontend
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        log_info "Installing frontend dependencies..."
        npm install
    fi
    
    # Build the frontend
    log_info "Building React application..."
    npm run build
    
    cd ../infrastructure
    log_info "Frontend build complete"
}

# Function to check and run database migrations
run_db_migrations() {
    log_step "Checking database migrations..."
    
    # Check if alembic is being used
    if [ -f "../backend/alembic.ini" ]; then
        log_info "Running Alembic migrations..."
        cd ../backend
        alembic upgrade head
        cd ../infrastructure
    else
        log_info "No migration tool detected. Tables will be created/updated by SQLAlchemy on startup."
    fi
}

# Function to deploy backend stack
deploy_backend() {
    log_step "Deploying backend stack..."
    
    log_info "Deploying CassidyBackendStack..."
    cdk deploy CassidyBackendStack --require-approval never
    
    # Get the API URL
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name CassidyBackendStack \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$API_URL" ]; then
        log_info "Backend deployed successfully!"
        log_info "API URL: $API_URL"
        echo "$API_URL" > .backend-url  # Save for frontend deployment
        
        # Run database migrations after deployment
        run_db_migrations
    else
        log_error "Failed to get API URL from backend stack"
        exit 1
    fi
}

# Function to deploy frontend stack
deploy_frontend() {
    log_step "Deploying frontend stack..."
    
    # Determine API URL
    API_URL=""
    
    # First try to get from saved file (if backend was just deployed)
    if [ -f ".backend-url" ]; then
        API_URL=$(cat .backend-url)
        log_info "Using API URL from recent backend deployment: $API_URL"
    else
        # Try to get from existing backend stack
        API_URL=$(aws cloudformation describe-stacks \
            --stack-name CassidyBackendStack \
            --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
            --output text 2>/dev/null || echo "")
        
        if [ -n "$API_URL" ]; then
            log_info "Using API URL from existing backend stack: $API_URL"
        else
            log_error "Cannot determine API URL. Deploy backend first or provide API URL."
            exit 1
        fi
    fi
    
    # Update app.py with the correct API URL
    log_info "Updating frontend configuration with API URL..."
    FULL_API_URL="${API_URL}/api/v1"
    
    # Use sed to update the API URL in app.py
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|api_url=\"[^\"]*\"|api_url=\"$FULL_API_URL\"|g" app.py
    else
        # Linux
        sed -i "s|api_url=\"[^\"]*\"|api_url=\"$FULL_API_URL\"|g" app.py
    fi
    
    log_info "Deploying CassidyFrontendStack..."
    cdk deploy CassidyFrontendStack --require-approval never
    
    # Get the CloudFront URL
    CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
        --stack-name CassidyFrontendStack \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$CLOUDFRONT_URL" ]; then
        log_info "Frontend deployed successfully!"
        log_info "Frontend URL: $CLOUDFRONT_URL"
        echo "$CLOUDFRONT_URL" > .frontend-url  # Save for CORS update
    else
        log_error "Failed to get CloudFront URL from frontend stack"
        exit 1
    fi
}

# Function to update CORS configuration
update_cors_config() {
    log_step "Updating CORS configuration..."
    
    # Get the CloudFront URL
    FRONTEND_URL=""
    if [ -f ".frontend-url" ]; then
        FRONTEND_URL=$(cat .frontend-url)
    else
        # Try to get from existing stack
        FRONTEND_URL=$(aws cloudformation describe-stacks \
            --stack-name CassidyFrontendStack \
            --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' \
            --output text 2>/dev/null || echo "")
    fi
    
    if [ -z "$FRONTEND_URL" ]; then
        log_warn "Frontend URL not available, skipping CORS update"
        return
    fi
    
    log_info "Updating CORS configuration for: $FRONTEND_URL"
    
    # Update main.py with the new CloudFront URL
    MAIN_PY="../backend/app/main.py"
    if [ -f "$MAIN_PY" ]; then
        # Check if URL already exists in CORS
        if grep -q "$FRONTEND_URL" "$MAIN_PY"; then
            log_info "CloudFront URL already in CORS configuration"
        else
            log_info "Adding CloudFront URL to CORS configuration"
            # Add the new URL to the allow_origins list
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS - add after the first allow_origins line
                sed -i '' "/allow_origins=\[/,/\]/ s/allow_origins=\[/allow_origins=[\n        \"$FRONTEND_URL\",  # Current CloudFront URL/" "$MAIN_PY"
            else
                # Linux
                sed -i "/allow_origins=\[/,/\]/ s/allow_origins=\[/allow_origins=[\n        \"$FRONTEND_URL\",  # Current CloudFront URL/" "$MAIN_PY"
            fi
            log_info "CORS configuration updated - backend redeploy required"
            echo "CORS_UPDATE_NEEDED=true" > .cors-update
        fi
    else
        log_error "Backend main.py not found"
    fi
}

# Function to update Flutter app configuration
update_flutter_config() {
    log_step "Updating Flutter app configuration..."
    
    if [ -f "update_flutter_api.py" ]; then
        log_info "Updating Flutter app API configuration..."
        python3 update_flutter_api.py || log_warn "Failed to update Flutter configuration"
    else
        log_warn "Flutter update script not found, skipping"
    fi
}

# Function to test deployment
test_deployment() {
    if [ "$SKIP_TEST" = "true" ]; then
        log_warn "Skipping deployment testing (--no-test specified)"
        return
    fi
    
    log_step "Testing deployment..."
    
    # First ensure test user exists
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name CassidyBackendStack \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    if [ -n "$API_URL" ] && [ -f "setup_test_user.py" ]; then
        log_info "Setting up test user..."
        python3 setup_test_user.py "$API_URL" || log_warn "Failed to setup test user"
    fi
    
    # Check if test script exists
    if [ -f "test_api_simple.py" ]; then
        log_info "Running API tests..."
        python3 test_api_simple.py "$API_URL"
    elif [ -f "test_api.sh" ]; then
        log_info "Running API tests..."
        ./test_api.sh
    else
        log_warn "No test script found, skipping tests"
    fi
}

# Function to clean up temporary files
cleanup() {
    rm -f .backend-url .frontend-url .cors-update
}

# Function to show deployment summary
show_summary() {
    log_step "Deployment Summary"
    
    # Get URLs from stacks
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name CassidyBackendStack \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
        --output text 2>/dev/null || echo "Not deployed")
    
    FRONTEND_URL=$(aws cloudformation describe-stacks \
        --stack-name CassidyFrontendStack \
        --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' \
        --output text 2>/dev/null || echo "Not deployed")
    
    echo ""
    echo "🎉 Deployment Complete!"
    echo "======================="
    echo ""
    echo "📊 Backend API: $API_URL"
    echo "🌐 Frontend:    $FRONTEND_URL"
    echo ""
    
    if [ "$API_URL" != "Not deployed" ] && [ "$FRONTEND_URL" != "Not deployed" ]; then
        echo "🔑 Test Credentials:"
        echo "   Username: user_123"
        echo "   Password: 1234"
        echo ""
        echo "🧪 Quick Test:"
        echo "   curl $API_URL/health"
        echo ""
    fi
}

# Main function
main() {
    # Parse command line arguments
    COMPONENT="both"
    CHECK_DEPS=false
    SKIP_BUILD=false
    SKIP_TEST=false
    FORCE=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --check-deps)
                CHECK_DEPS=true
                shift
                ;;
            --no-build)
                SKIP_BUILD=true
                shift
                ;;
            --no-test)
                SKIP_TEST=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            backend|frontend|both)
                COMPONENT=$1
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Set trap for cleanup
    trap cleanup EXIT
    
    echo "🚀 Cassidy Infrastructure Deployment"
    echo "===================================="
    echo ""
    log_info "Component: $COMPONENT"
    echo ""
    
    # Check dependencies if requested
    if [ "$CHECK_DEPS" = "true" ]; then
        check_dependencies
    fi
    
    # Confirm deployment unless forced
    if [ "$FORCE" != "true" ]; then
        echo -e "${YELLOW}Continue with deployment? (y/N):${NC}"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log_info "Deployment cancelled"
            exit 0
        fi
    fi
    
    # Check dependencies and AWS parameters
    check_dependencies
    check_aws_parameters
    
    # Deploy based on component
    case $COMPONENT in
        "backend")
            deploy_backend
            update_flutter_config
            ;;
        "frontend")
            build_frontend
            deploy_frontend
            update_cors_config
            ;;
        "both")
            deploy_backend
            build_frontend
            deploy_frontend
            update_cors_config
            update_flutter_config
            
            # Check if CORS update requires backend redeploy
            if [ -f ".cors-update" ]; then
                log_info "CORS configuration changed, redeploying backend..."
                rm -f .cors-update
                deploy_backend
                update_flutter_config
            fi
            ;;
        *)
            log_error "Invalid component: $COMPONENT"
            exit 1
            ;;
    esac
    
    # Test deployment
    test_deployment
    
    # Show summary
    show_summary
    
    log_info "🎉 All done!"
}

# Run main function
main "$@"