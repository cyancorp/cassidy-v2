# Cassidy AI Journaling Assistant

A comprehensive AI-powered journaling platform with web and mobile applications, powered by pydantic-ai and Anthropic's Claude.

## Project Structure

This is a monorepo containing all components of the Cassidy platform:

```
cassidy-claudecode/
├── backend/           # FastAPI backend with pydantic-ai agent
├── frontend/          # React web application
├── mobile_flutter/   # Flutter mobile app (iOS & Android)
└── infrastructure/   # AWS CDK deployment configuration
```

## Features

- **AI-Powered Journaling**: Intelligent journaling assistant using Claude
- **Multi-Platform**: Web and mobile applications with consistent UX
- **Structured Journaling**: Automatic structuring of journal entries
- **User Preferences**: Personalized AI responses based on user goals
- **Secure Authentication**: JWT-based authentication system
- **Cloud Deployment**: Serverless deployment on AWS Lambda

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 16+
- Flutter SDK 3.0+
- Docker (for deployment)
- AWS CLI (for deployment)
- Xcode (for iOS development)
- Android Studio (for Android development)

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Mobile Development (Flutter)

```bash
cd mobile_flutter
flutter pub get

# iOS
flutter run

# Android (requires Android emulator or device)
flutter run

# Web (for testing)
flutter run -d web
```

## Documentation

- [Backend Documentation](./backend/README.md)
- [Mobile App Documentation](./mobile_flutter/README.md)
- [Deployment Guide](./infrastructure/README.md)

## Testing

### Backend Tests
```bash
cd backend
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Mobile Tests (Flutter)
```bash
cd mobile_flutter
flutter test
```

## Deployment

### Quick Start Deployment

The easiest way to deploy is using the unified deployment script:

```bash
# Deploy both frontend and backend
cd infrastructure
./deploy.sh

# Deploy only backend
./deploy.sh backend

# Deploy only frontend  
./deploy.sh frontend

# Deploy with options
./deploy.sh both --no-test     # Skip tests
./deploy.sh backend --force     # Skip confirmation
```

### Production URLs

After deployment, the application will be available at:

- **Backend API**: Dynamic URL (check deployment output)
- **Frontend Web App**: Dynamic CloudFront URL (check deployment output)

**URL Stability**: URLs are stable within a deployment but will change if infrastructure is torn down and recreated.

### Prerequisites for Deployment

1. **AWS CLI configured** with appropriate permissions
2. **AWS CDK installed** (`npm install -g aws-cdk`)
3. **Docker** installed (for Lambda container deployment)
4. **Node.js 16+** and **Python 3.11+**

### Required AWS Parameters

Before first deployment, create these secure parameters:

```bash
# JWT secret key
aws ssm put-parameter \
  --name "/cassidy/jwt-secret-key" \
  --value "your-secure-jwt-secret" \
  --type "SecureString"

# Anthropic API key  
aws ssm put-parameter \
  --name "/cassidy/anthropic-api-key" \
  --value "your-anthropic-api-key" \
  --type "SecureString"
```

### Deployment Scripts

#### Main Deployment Script (`deploy.sh`)

```bash
# Deploy everything (recommended for first deployment)
./deploy.sh

# Deploy specific components
./deploy.sh backend    # Backend only
./deploy.sh frontend   # Frontend only
./deploy.sh both       # Both stacks (default)

# Options
--force       # Skip confirmation prompt
--no-test     # Skip post-deployment tests
--no-build    # Skip frontend build (frontend deployment only)
--check-deps  # Check dependencies before deployment
```

Features:
- Automatic CORS configuration updates
- Database migration support
- Test user creation
- Comprehensive testing
- Automatic frontend configuration with backend URL

#### Complete Reset (`reset_and_deploy.sh`)

For a complete teardown and fresh deployment:

```bash
./reset_and_deploy.sh
```

⚠️ **Warning**: This will delete ALL resources including databases!

#### Infrastructure Teardown (`teardown.sh`)

To remove all AWS resources:

```bash
./teardown.sh
```

This will delete:
- CloudFormation stacks
- RDS databases (with deletion protection disabled)
- Lambda functions
- S3 buckets and contents
- API Gateway APIs
- VPCs and networking resources
- SSM parameters (except CDK bootstrap)

### Database Schema Updates

The deployment automatically handles database schema updates:

1. **SQLAlchemy Auto-migration**: Tables are created/updated on Lambda startup
2. **Alembic Support**: If `alembic.ini` exists, migrations run automatically
3. **Zero-downtime**: Schema updates don't require downtime

### Architecture Overview

- **Backend**: AWS Lambda (containerized) + API Gateway + RDS PostgreSQL
- **Frontend**: React SPA on S3 + CloudFront CDN
- **Database**: RDS PostgreSQL (publicly accessible, encrypted)
- **Infrastructure**: AWS CDK with separate stacks for independent deployment

### Stack Details

1. **CassidyBackendStack**:
   - Lambda function (no VPC for internet access)
   - API Gateway REST API
   - RDS PostgreSQL in minimal VPC
   - Secrets Manager for DB credentials
   - SSM Parameters for configuration

2. **CassidyFrontendStack**:
   - S3 bucket for static hosting
   - CloudFront distribution
   - Automatic API URL injection
   - SPA routing support

### Deployment Best Practices

1. **Initial Deployment**: Use `./deploy.sh` to deploy both stacks
2. **Code Updates**: Deploy only the changed component
3. **CORS Updates**: Automatic when deploying frontend
4. **Database Changes**: Handled automatically via SQLAlchemy
5. **Testing**: Always included unless `--no-test` specified

### Troubleshooting Deployment

```bash
# Check Lambda logs
aws logs tail /aws/lambda/CassidyBackendStack-CassidyFunction

# Check stack status
aws cloudformation describe-stacks --stack-name CassidyBackendStack

# Test API health
curl $(aws cloudformation describe-stacks \
  --stack-name CassidyBackendStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)/health

# Create test user if needed
python3 infrastructure/setup_test_user.py <API_URL>
```

### Getting a Custom Domain

To get a cleaner URL for the frontend:

1. **Register a domain** through AWS Route 53 or your preferred registrar
2. **Configure CDK** with domain name:
   ```bash
   cd infrastructure
   cdk deploy --context domain_name=yourdomain.com
   ```
3. **Frontend will be available at**: `https://yourdomain.com`
4. **API will be available at**: `https://api.yourdomain.com`

### Troubleshooting Deployment

**Lambda Function Errors**: Check AWS CloudWatch logs
```bash
# View recent logs
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/cassidy-api
```

**Database Connection Issues**: Verify RDS is running and security groups allow Lambda access

**CORS Issues**: Ensure frontend URL is properly configured in the Lambda stack

## Architecture

- **Backend**: FastAPI + pydantic-ai + SQLAlchemy
- **Frontend**: React + TypeScript + Vite
- **Mobile**: Flutter + Dart
- **AI**: Anthropic Claude via pydantic-ai
- **Database**: SQLite (local) / PostgreSQL (production)
- **Deployment**: AWS Lambda + API Gateway + CDK

## Contributing

1. Create a feature branch
2. Make your changes
3. Write/update tests
4. Ensure all tests pass
5. Submit a pull request

### Test Credentials

Default test user (created automatically during deployment):
- **Username**: `user_123`
- **Password**: `1234`

## License

This project is private and proprietary.

