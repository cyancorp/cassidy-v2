#!/usr/bin/env python3
"""
CDK App entry point for Cassidy AI Journaling Assistant
"""
import aws_cdk as cdk
from stacks.lambda_stack import CassidyLambdaStack

app = cdk.App()

# Get environment configuration
env = cdk.Environment(
    account=app.node.try_get_context("account"),  # Will use current AWS credentials
    region=app.node.try_get_context("region") or "us-east-1"
)

# Create the Lambda-based stack
CassidyLambdaStack(
    app, 
    "CassidyLambdaStack",
    env=env,
    description="Cassidy AI Journaling Assistant - Serverless Lambda deployment"
)

app.synth()