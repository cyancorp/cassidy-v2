# Cassidy AI - AWS Infrastructure

This directory contains the AWS CDK infrastructure and deployment scripts for the Cassidy AI Journaling Assistant.

## Architecture Overview

### Backend Stack (CassidyBackendStack)
- **AWS Lambda**: Containerized FastAPI app (NO VPC for internet access)
- **API Gateway**: REST API with automatic CORS configuration
- **RDS PostgreSQL**: Publicly accessible database in minimal VPC
- **Secrets Manager**: Database credentials management
- **SSM Parameters**: Application configuration

### Frontend Stack (CassidyFrontendStack)  
- **S3 Bucket**: Static website hosting for React SPA
- **CloudFront**: CDN with HTTPS, caching, and SPA routing
- **Dynamic Configuration**: API URL injected at deployment

## Quick Start

### Prerequisites

1. **AWS CLI configured** with appropriate credentials
2. **AWS CDK installed**: `npm install -g aws-cdk`
3. **Docker** for Lambda container builds
4. **SSM Parameters created**:
   ```bash
   aws ssm put-parameter --name "/cassidy/jwt-secret-key" --value "your-jwt-secret" --type "SecureString"
   aws ssm put-parameter --name "/cassidy/anthropic-api-key" --value "sk-ant-..." --type "SecureString"
   ```

### Deployment Scripts

#### 🚀 Main Deployment (`deploy.sh`)

The primary deployment script with automatic CORS updates and testing:

```bash
# Deploy everything (recommended)
./deploy.sh

# Deploy specific components
./deploy.sh backend     # Backend only
./deploy.sh frontend    # Frontend only

# With options
./deploy.sh --force          # Skip confirmation
./deploy.sh --no-test        # Skip tests
./deploy.sh --no-build       # Skip frontend build
./deploy.sh backend --force  # Force backend deployment
```

**Features**:
- ✅ Automatic CORS configuration updates
- ✅ Database migration support
- ✅ Test user creation
- ✅ Comprehensive API testing
- ✅ Frontend automatically configured with backend URL

#### 🔥 Complete Reset (`reset_and_deploy.sh`)

For a complete teardown and fresh deployment:

```bash
./reset_and_deploy.sh
```

⚠️ **Warning**: This deletes ALL resources including databases!

#### 🗑️ Teardown (`teardown.sh`)

Remove all AWS resources (preserves CDK bootstrap):

```bash
./teardown.sh
```

### Testing Tools

#### API Testing (`test_api_simple.py`)

Comprehensive test suite using only Python standard library:

```bash
# Test with current deployment
python3 test_api_simple.py

# Test specific API
python3 test_api_simple.py https://your-api.amazonaws.com/prod

# With custom credentials
python3 test_api_simple.py <API_URL> <username> <password>
```

#### Setup Test User (`setup_test_user.py`)

Create test user for production environments:

```bash
python3 setup_test_user.py <API_URL>
```

## Database Schema Management

### Automatic Schema Updates

The deployment handles database schema changes automatically:

1. **SQLAlchemy Auto-creation**: Tables are created on first deployment
2. **Schema Evolution**: New columns/tables added automatically
3. **Alembic Support**: If `alembic.ini` exists in backend, migrations run during deployment
4. **Zero Downtime**: Schema updates don't require service interruption

### Manual Database Access

```bash
# Get database endpoint
aws cloudformation describe-stacks \
  --stack-name CassidyBackendStack \
  --query 'Stacks[0].Outputs[?OutputKey==`DatabaseEndpoint`].OutputValue' \
  --output text

# Get database password
aws secretsmanager get-secret-value \
  --secret-id <SecretArn> \
  --query SecretString \
  --output text | jq -r .password
```

## Stack Configuration Details

### Backend Stack Components

1. **Lambda Function** (Container-based)
   - No VPC configuration for internet access
   - 1GB memory, 30s timeout
   - Container image with all dependencies
   - Mangum adapter for FastAPI

2. **API Gateway**
   - REST API with proxy integration
   - Automatic request routing to Lambda
   - CloudWatch logging enabled

3. **RDS PostgreSQL**
   - t3.micro instance (cost-optimized)
   - 20GB storage with autoscaling to 100GB
   - Public accessibility enabled
   - 7-day backup retention
   - Deletion protection enabled

4. **Networking**
   - Lambda: No VPC (AWS managed)
   - Database: Minimal VPC with public subnets
   - Security group allows PostgreSQL from anywhere

### Frontend Stack Components

1. **S3 Bucket**
   - Static website hosting enabled
   - Public read access for web content
   - Automatic cleanup on stack deletion

2. **CloudFront Distribution**
   - HTTPS termination
   - Global edge caching
   - SPA routing (404→index.html)
   - Automatic cache invalidation on deployment

3. **Dynamic Configuration**
   - API URL injected via env-config.js
   - No rebuild required for URL changes

## CORS Management

CORS is automatically managed by the deployment script:

1. **Automatic Updates**: When deploying frontend, CORS is updated in backend
2. **Hardcoded Origins**: Due to Lambda constraints, origins are in `main.py`
3. **Multiple Environments**: Supports localhost, S3, and CloudFront URLs

## Troubleshooting

### Common Issues

1. **503 Database Connection Error**
   - Usually means no test user exists
   - Run: `python3 setup_test_user.py <API_URL>`

2. **CORS Errors**
   - Check CloudFront URL in browser console
   - Verify URL is in `backend/app/main.py` CORS origins
   - Redeploy backend after CORS changes

3. **Lambda Timeout (30s)**
   - Usually network/VPC issue
   - Ensure Lambda has NO VPC configuration
   - Check CloudWatch logs

4. **Container Build Fails**
   - Ensure Docker is running
   - Check ECR repository exists
   - Run `cdk bootstrap` if needed

### Monitoring

```bash
# Check Lambda logs
aws logs tail /aws/lambda/CassidyBackendStack-CassidyFunction --follow

# Check API Gateway logs
aws logs tail API-Gateway-Execution-Logs --follow

# View stack events
aws cloudformation describe-stack-events --stack-name CassidyBackendStack
```

## Cost Optimization

The infrastructure is designed for MVP cost efficiency:

- **Lambda**: Pay per request, no idle costs
- **RDS**: t3.micro instance (~$15/month)
- **S3 + CloudFront**: Minimal storage and transfer costs
- **No NAT Gateway**: Saves ~$45/month
- **No VPC Endpoints**: Saves additional costs

Estimated monthly cost: ~$20-30 for light usage

## Security Considerations

- **Database**: Encrypted at rest, publicly accessible but password-protected
- **API**: HTTPS only via API Gateway and CloudFront
- **Secrets**: Stored in AWS Secrets Manager and SSM Parameter Store
- **CORS**: Restricted to specific frontend domains
- **Authentication**: JWT tokens with 24-hour expiration

## Contributing

1. Test changes locally with `cdk synth`
2. Deploy to personal AWS account first
3. Run full test suite
4. Submit PR with test results

## License

This project is proprietary software for Cassidy AI Journaling Assistant.
