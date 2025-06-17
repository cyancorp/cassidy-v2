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

### Production URLs

After deployment, the application will be available at these URLs:

- **Backend API**: `https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod`
- **Frontend Web App**: `https://donx85isqomd0.cloudfront.net` (CloudFront CDN with HTTPS)

**URL Stability**: These URLs are stable and will not change unless you redeploy the infrastructure from scratch. Regular code deployments maintain the same URLs.

### Prerequisites for Deployment

1. **AWS CLI configured** with appropriate permissions
2. **AWS CDK installed** (`npm install -g aws-cdk`)
3. **Environment variables set** in AWS Systems Manager Parameter Store

### Required AWS Parameters

Before deploying, you must create these secure parameters in AWS Systems Manager:

```bash
# JWT secret key
aws ssm put-parameter --name "/cassidy/jwt-secret-key" --value "your-secure-jwt-secret" --type "SecureString"

# Anthropic API key  
aws ssm put-parameter --name "/cassidy/anthropic-api-key" --value "your-anthropic-api-key" --type "SecureString"
```

### Deploy Both Stacks (Recommended)

To deploy both backend and frontend together:

```bash
# 1. Navigate to infrastructure directory
cd infrastructure
npm install

# 2. Build frontend first
cd ../frontend && npm run build && cd ../infrastructure

# 3. Deploy both stacks
cdk deploy --all --require-approval never
```

### Deploy Backend Only

To deploy backend code changes to AWS Lambda:

```bash
# 1. Navigate to infrastructure directory
cd infrastructure

# 2. Deploy the backend stack
cdk deploy CassidyLambdaStackFixed --require-approval never

# 3. Verify deployment
curl https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod/health
```

### Deploy Frontend Only

To deploy frontend changes to S3 + CloudFront:

```bash
# 1. Build the frontend
cd frontend
npm run build

# 2. Deploy frontend stack
cd ../infrastructure
cdk deploy CassidyFrontendStack --require-approval never
```

**Note**: The deployment process automatically:
- Bundles the backend code with dependencies
- Updates the Lambda function 
- Maintains the existing API Gateway and database
- Preserves all data in the RDS PostgreSQL database
- Frontend deployment updates S3 bucket and invalidates CloudFront cache

### Architecture Overview

- **Backend**: AWS Lambda + API Gateway + RDS PostgreSQL (CassidyLambdaStackFixed)
- **Frontend**: S3 Static Website Hosting + CloudFront CDN (CassidyFrontendStack)
- **Database**: AWS RDS PostgreSQL (persistent across deployments)
- **Infrastructure**: Managed via AWS CDK with separate stacks for independent deployment

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

## License

This project is private and proprietary.









  🌐 Frontend URL for Testing

  Primary Frontend URL (HTTPS with CloudFront CDN):
  https://donx85isqomd0.cloudfront.net

  Backup S3 Direct URL:
  http://cassidy-frontend-538881967423.s3-website-us-east-1.amazonaws.com

  🔑 Test Credentials

  - Username: user_123
  - Password: 1234

  📊 API Endpoint Summary

  - ✅ Root: https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod/
  - ✅ Health: https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod/health
  - ✅ Login: https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod/api/v1/auth/login
  - ✅ Documentation: https://tamep5ms5i.execute-api.us-east-1.amazonaws.com/prod/docs


  # Quick test after deployment
  cd infrastructure
  ./test_api.sh

  # More detailed testing
  python3 test_api_simple.py

  # One-line deploy and test
  cdk deploy CassidyLambdaStackFixed --require-approval never && ./test_api.sh