# Cassidy AI - AWS Lambda Infrastructure

This directory contains the AWS CDK infrastructure for deploying the Cassidy AI Journaling Assistant as a serverless application using AWS Lambda, API Gateway, and RDS PostgreSQL.

## Architecture

### Backend Stack (CassidyLambdaStackFixed)
- **API Gateway**: REST API with CORS configuration
- **AWS Lambda**: FastAPI application using Mangum adapter
- **RDS PostgreSQL**: Database with VPC isolation and SSL
- **VPC**: Private subnets for database, VPC endpoints for AWS services
- **Secrets Manager**: Database credentials management

### Frontend Stack (CassidyFrontendStack)  
- **S3 Bucket**: Static website hosting for React application
- **CloudFront**: CDN with HTTPS termination and caching
- **Dynamic Configuration**: API URL injected via env-config.js

## Deployment

### Backend Deployment
```bash
# Install CDK dependencies
npm install

# Deploy backend stack
cdk deploy CassidyLambdaStackFixed --require-approval never
```

### Frontend Deployment
```bash
# Build frontend
cd ../frontend
npm run build

# Deploy frontend stack  
cd ../infrastructure
cdk deploy CassidyFrontendStack --require-approval never
```

### Deploy Both Stacks
```bash
# Install dependencies
npm install

# Build frontend first
cd ../frontend && npm run build && cd ../infrastructure

# Deploy both stacks
cdk deploy --all --require-approval never
```

### Individual Stack Management
```bash
# Deploy only backend
cdk deploy CassidyLambdaStackFixed

# Deploy only frontend  
cdk deploy CassidyFrontendStack

# List all stacks
cdk list

# Destroy specific stack
cdk destroy CassidyFrontendStack
```

## Known Issues and Solutions

### 1. Lambda Size Constraints and Container Deployment ✅ RESOLVED

**Problem**: Lambda deployment fails with "Unzipped size must be smaller than 262144000 bytes" when including AI dependencies (pydantic-ai-slim[anthropic]).

**Root Cause**: ZIP deployment has a 250MB unzipped size limit, but AI dependencies are larger than this limit.

**Solution**: Use container deployment instead of ZIP deployment in the Lambda stack:

```python
# ❌ BROKEN - ZIP deployment exceeds size limit
lambda_function = lambda_.Function(
    runtime=lambda_.Runtime.PYTHON_3_11,
    code=lambda_.Code.from_asset("../backend", bundling=...),
    ...
)

# ✅ WORKING - container deployment has no size limit
lambda_function = lambda_.Function(
    runtime=lambda_.Runtime.FROM_IMAGE,
    code=lambda_.Code.from_asset_image("../backend"),
    ...
)
```

**Required Files**:
- `/backend/Dockerfile` - Container image definition
- `/backend/requirements-lambda-minimal.txt` - Full dependencies including AI packages

**Frontend-Backend Contract**: The frontend expects these endpoints to be available:
- ✅ `POST /api/v1/sessions` - Create chat sessions
- ✅ `GET /api/v1/user/preferences` - Load user preferences  
- ✅ `GET /api/v1/user/template` - Load journal template
- ✅ `POST /api/v1/agent/chat/{session_id}` - Send messages to AI agent

### 2. CORS Configuration Issues

**Problem**: FastAPI CORS middleware using `settings.CORS_ORIGINS` fails in Lambda environment, resulting in missing `Access-Control-Allow-Origin` headers.

**Root Cause**: pydantic-settings List fields don't properly fall back to default values when environment variables are missing in Lambda.

**Solution**: Use hardcoded CORS origins in `main.py` instead of `settings.CORS_ORIGINS`:

```python
# ❌ BROKEN in Lambda
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Returns empty list in Lambda
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ WORKING solution
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://cassidy-frontend-1748872354.s3-website-us-east-1.amazonaws.com",
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://localhost:5174"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Alternative Solutions**:
- Set `CORS_ORIGINS` as Lambda environment variable in CDK
- Use property method instead of direct pydantic field
- Add validation to ensure defaults are used

### 2. Database Connection Issues

**Problem**: 503 Service Unavailable errors with "Database connection unavailable" message.

**Root Cause**: `DATABASE_URL` was being evaluated at module import time before Lambda environment had AWS credentials available.

**Solution**: Make database URL retrieval dynamic at runtime:

```python
# ❌ BROKEN - evaluated at import time
class Settings(BaseSettings):
    DATABASE_URL: str = get_database_url()  # Called before AWS credentials available

# ✅ WORKING - evaluated at runtime
async def init_db():
    from app.core.database_url import get_database_url
    database_url = get_database_url()  # Called when Lambda has credentials
```

**Files Changed**:
- `backend/app/core/config.py`: Set `DATABASE_URL = ""`
- `backend/app/database.py`: Dynamic URL retrieval in `init_db()`

### 3. Database Password Special Characters

**Problem**: PostgreSQL authentication fails with special characters in auto-generated passwords.

**Root Cause**: Special characters in passwords need URL encoding for connection strings.

**Solution**: URL encode username and password in `database_url.py`:

```python
import urllib.parse

# URL encode credentials
encoded_username = urllib.parse.quote(username, safe='')
encoded_password = urllib.parse.quote(password, safe='')

final_url = f"postgresql+asyncpg://{encoded_username}:{encoded_password}@{host}:{port}/cassidy"
```

### 4. Lambda Cold Start and Database Initialization

**Problem**: Database initialization failures on Lambda cold starts causing subsequent requests to fail.

**Solution**: Graceful fallback with per-request initialization:

```python
async def get_db():
    global engine, async_session_maker
    
    # If engine not initialized, try to initialize now
    if engine is None or async_session_maker is None:
        try:
            await init_db()
        except Exception as e:
            print(f"Failed to initialize database in get_db: {e}")
            raise HTTPException(status_code=503, detail="Database connection unavailable")
```

### 5. Lambda VPC Networking - Critical Issue ⚠️ MAJOR BLOCKER

**Problem**: Lambda in private VPC subnets cannot reach external APIs (Anthropic), causing 30-second timeouts when sending messages to the agent.

**Root Cause**: Lambda placed in `PRIVATE_ISOLATED` subnets has no internet access to reach Anthropic API endpoints, but needs VPC access for RDS database connectivity.

**Error Pattern**:
- ✅ Database connection works
- ✅ Agent context creation works  
- ✅ Message history loading works
- ❌ Agent initialization times out after 30 seconds (cannot reach Anthropic API)

**Solution**: Lambda must be placed in **public subnets** with internet gateway access:

```python
# ❌ BROKEN - Lambda in private subnets (no internet access)
vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED)

# ✅ WORKING - Lambda in public subnets (internet + VPC access)
vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
allow_public_subnet=True  # Required by AWS CDK
```

**VPC Architecture**:
```
VPC (10.1.0.0/16)
├── Public Subnets (10.1.0.0/24, 10.1.1.0/24)
│   ├── Lambda Functions (internet access for Anthropic API)
│   └── Internet Gateway
└── Private Subnets (10.1.2.0/24, 10.1.3.0/24)  
    └── RDS Database (security isolation)
```

**Security Groups**:
- Lambda SG: Outbound HTTPS (443) for Anthropic API + PostgreSQL (5432) for RDS
- RDS SG: Inbound PostgreSQL (5432) from Lambda SG only

**Cost Impact**: Zero additional cost (public subnets and internet gateways are free)

### 6. Anthropic API Key Management

**Problem**: Agent timeouts when API key is loaded from SSM Parameter Store through VPC endpoints.

**Root Cause**: SSM VPC endpoint calls have high latency/timeout in private subnets.

**Solution**: Set API key directly as Lambda environment variable for fast access:

```python
# CDK Lambda configuration
environment={
    "ANTHROPIC_API_KEY": "sk-ant-api03-...",  # Direct environment variable
    "ANTHROPIC_API_KEY_PARAM": "/cassidy/anthropic-api-key",  # Fallback
}
```

**API Key Loading Priority**:
1. `ANTHROPIC_API_KEY` environment variable (fastest)
2. SSM Parameter Store via `ANTHROPIC_API_KEY_PARAM` (fallback)

### 7. SSL/TLS Configuration for RDS

**Problem**: SSL connection issues between Lambda and RDS.

**Solution**: Configure SSL context for asyncpg connections:

```python
def create_ssl_context():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context

# Use in Lambda environment
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    connect_args["ssl"] = create_ssl_context()
```

## Debugging Tips

### 1. Check CloudWatch Logs
```bash
# View Lambda logs
aws logs tail /aws/lambda/cassidy-api --follow
```

### 2. Test Database Connectivity
Database connection can be tested via the health endpoint:
```bash
curl https://s7blicf22g.execute-api.us-east-1.amazonaws.com/prod/health
```

### 3. CORS Testing
Test CORS headers with curl:
```bash
curl -v -H "Origin: http://cassidy-frontend-1748872354.s3-website-us-east-1.amazonaws.com" \
  -H "Content-Type: application/json" \
  -d '{"username":"user_123","password":"1234"}' \
  https://s7blicf22g.execute-api.us-east-1.amazonaws.com/prod/api/v1/auth/login
```

Look for:
- ✅ `access-control-allow-origin: http://cassidy-frontend-1748872354.s3-website-us-east-1.amazonaws.com`
- ✅ `access-control-allow-credentials: true`
- ✅ `vary: Origin`

### 4. Common Error Patterns

- **502 Bad Gateway**: Lambda function crashed (check CloudWatch logs)
- **503 Service Unavailable**: Database connection issues
- **Missing CORS headers**: pydantic-settings List field issue
- **Import errors**: Missing dependencies in requirements-lambda-minimal.txt

### 8. CloudFormation Stack Management Issues

**Problem**: CDK deployment failures due to VPC CIDR conflicts and RDS subnet group constraints.

**Root Cause**: 
- VPC CIDR changes require new subnet creation but conflict with existing subnets
- RDS subnet groups cannot be moved between VPCs in updates
- Stack gets into `UPDATE_ROLLBACK_COMPLETE` state

**Solutions**:

1. **For VPC Architecture Changes**: Deploy fresh stack with new name:
```bash
# Tear down existing stack
cdk destroy CassidyLambdaStack --force

# Deploy with new VPC configuration  
cdk deploy CassidyNewStack --require-approval never
```

2. **For Minor Updates**: Use `--disable-rollback` during development:
```bash
cdk deploy --disable-rollback --require-approval never
```

3. **Emergency Fixes**: Update Lambda configuration directly via AWS CLI:
```bash
# Remove Lambda from VPC temporarily
aws lambda update-function-configuration \
  --function-name CassidyLambdaStack-CassidyFunction \
  --vpc-config 'SubnetIds=[],SecurityGroupIds=[]'

# Update environment variables
aws lambda update-function-configuration \
  --function-name CassidyLambdaStack-CassidyFunction \
  --environment '{"Variables":{"ANTHROPIC_API_KEY":"sk-ant-..."}}'
```

## Deployment Rules

Based on troubleshooting experience:

1. **NEVER deploy complex changes to cloud without local testing first**
2. **ALWAYS test minimal viable version before adding features**
3. **ALWAYS verify frontend-backend API contracts match exactly**
4. **For Lambda: start with minimal dependencies, avoid compiled packages**
5. **Test with actual frontend requests, not just curl commands**
6. **Check CloudWatch logs first for Lambda import/runtime errors**
7. **Deploy incrementally: minimal → auth → core logic → complex features**
8. **For VPC changes: tear down and redeploy fresh stack to avoid conflicts**

## Environment Variables

The Lambda function expects these environment variables (set automatically by CDK):

- `AWS_LAMBDA_FUNCTION_NAME`: Set by Lambda runtime
- `DB_SECRET_ARN`: RDS credentials secret ARN
- `DATABASE_URL`: PostgreSQL connection string template
- `APP_ENV`: "production"
- `PYDANTIC_AI_SLIM`: "true"

## Security Considerations

- Database is in private VPC subnets (no public access)
- RDS credentials stored in AWS Secrets Manager
- SSL encryption for database connections
- CORS restricted to specific frontend domains
- No hardcoded secrets in code

## Cost Optimization

- Single AZ deployment for RDS (not multi-AZ)
- t3.micro instance for RDS
- No NAT Gateway (Lambda uses VPC endpoints)
- Minimal Lambda memory allocation (1024MB)
- VPC endpoints only for required services

## Monitoring

- CloudWatch Logs for Lambda execution
- X-Ray tracing enabled
- API Gateway metrics and logging
- RDS connection logging enabled

## Testing

### Automated Test Scripts

Two test scripts are provided to verify deployment health:

#### Bash Test Script
```bash
# Quick test with bash script
cd infrastructure
./test_api.sh

# With custom API URL
API_URL=https://your-api.amazonaws.com/prod ./test_api.sh

# With custom credentials
TEST_USERNAME=myuser TEST_PASSWORD=mypass ./test_api.sh
```

#### Python Test Scripts

**Full-featured script** (requires `requests` library):
```bash
# Install requests first
pip install requests  # or use virtual environment

# Run comprehensive test suite
cd infrastructure
python test_api.py

# With custom parameters
python test_api.py --api-url https://your-api.amazonaws.com/prod --username myuser --password mypass
```

**Simple script** (no dependencies - standard library only):
```bash
# Run basic test suite with Python 3 standard library
cd infrastructure
python3 test_api_simple.py

# With custom parameters
python3 test_api_simple.py https://your-api.amazonaws.com/prod myuser mypass
```

### Test Coverage

The test scripts validate:
1. ✅ Root endpoint accessibility
2. ✅ Health check endpoint
3. ✅ API documentation (Swagger)
4. ✅ Authentication flow (login)
5. ✅ Invalid credential handling
6. ✅ Authenticated user profile access
7. ✅ User preferences retrieval
8. ✅ Chat session creation
9. ✅ Agent message handling
10. ✅ Session message history
11. ✅ CORS preflight requests
12. ✅ Rate limiting (if configured)

### Running Tests After Deployment

```bash
# Deploy and test in one command
cdk deploy CassidyLambdaStackFixed --require-approval never && python test_api.py
```

## Troubleshooting Checklist

When deployment issues occur:

1. [ ] Run test scripts to identify failing endpoints
2. [ ] Check CloudWatch logs for Lambda errors
3. [ ] Verify VPC security groups allow Lambda → RDS communication  
4. [ ] Confirm Secrets Manager permissions for Lambda role
5. [ ] Test database connectivity from Lambda
6. [ ] Verify CORS configuration (hardcoded vs settings)
7. [ ] Check API Gateway CORS vs FastAPI CORS conflicts
8. [ ] Validate SSL context for RDS connections
9. [ ] Confirm environment variables are set correctly