#!/bin/bash

# Complete reset and clean deployment script
# This script tears down everything and deploys fresh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "🔥 Complete Cassidy Infrastructure Reset & Deploy"
echo "================================================"
echo ""
log_warn "This will completely destroy and recreate all Cassidy infrastructure!"
echo ""
read -p "Are you absolutely sure? Type 'reset' to continue: " -r
echo

if [[ $REPLY != "reset" ]]; then
    log_info "Reset cancelled"
    exit 0
fi

# Step 1: Complete teardown
log_info "Step 1: Running complete teardown..."
./teardown.sh

# Step 2: Clean local build artifacts
log_info "Step 2: Cleaning local build artifacts..."
rm -rf cdk.out/ 2>/dev/null || true
rm -f .backend-url .frontend-url 2>/dev/null || true

# Step 3: Verify AWS parameters exist
log_info "Step 3: Checking required AWS parameters..."
if ! aws ssm get-parameter --name "/cassidy/jwt-secret-key" --with-decryption &> /dev/null; then
    log_error "Missing /cassidy/jwt-secret-key parameter"
    echo "Create it with: aws ssm put-parameter --name '/cassidy/jwt-secret-key' --value 'your-jwt-secret' --type 'SecureString'"
    exit 1
fi

if ! aws ssm get-parameter --name "/cassidy/anthropic-api-key" --with-decryption &> /dev/null; then
    log_error "Missing /cassidy/anthropic-api-key parameter"
    echo "Create it with: aws ssm put-parameter --name '/cassidy/anthropic-api-key' --value 'your-anthropic-key' --type 'SecureString'"
    exit 1
fi

log_info "All required parameters are present"

# Step 4: Deploy fresh infrastructure
log_info "Step 4: Deploying fresh infrastructure..."
./deploy.sh both --force

log_info "🎉 Complete reset and deployment finished!"
log_info "Your Cassidy infrastructure is now fresh and clean!"