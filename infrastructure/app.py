#!/usr/bin/env python3
"""
CDK App entry point for Cassidy AI Journaling Assistant
"""
import aws_cdk as cdk
from stacks.backend_stack import BackendStack
from stacks.frontend_stack import FrontendStack

app = cdk.App()

# Get environment configuration
env = cdk.Environment(
    account=app.node.try_get_context("account"),  # Will use current AWS credentials
    region=app.node.try_get_context("region") or "us-east-1"
)

backend_stack = BackendStack(
    app, 
    "CassidyBackendStack",
    env=env,
    description="Cassidy AI Journaling Assistant - Backend with full internet access"
)

# Create the frontend stack with S3 static website hosting
frontend_stack = FrontendStack(
    app,
    "CassidyFrontendStack", 
    api_url="https://tq68ditf6b.execute-api.us-east-1.amazonaws.com/prod/api/v1",
    env=env,
    description="Cassidy AI Journaling Assistant - Frontend S3 static website with CloudFront"
)

app.synth()