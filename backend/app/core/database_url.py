"""
Database URL configuration with proper SSL handling for RDS
"""
import os
import json
import boto3
import ssl
import urllib.parse
from typing import Optional, Dict, Any


def get_rds_credentials() -> Optional[Dict[str, Any]]:
    """Get RDS credentials from AWS Secrets Manager"""
    secret_arn = os.environ.get("DB_SECRET_ARN")
    if not secret_arn:
        return None
        
    try:
        secrets_client = boto3.client('secretsmanager')
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Failed to get RDS credentials: {e}")
        return None


def create_ssl_context():
    """Create SSL context for RDS connections"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def get_database_url() -> str:
    """Get database URL with RDS credentials"""
    
    # Default to SQLite for local development
    default_url = "sqlite+aiosqlite:///./cassidy.db"
    database_url = os.environ.get("DATABASE_URL", default_url)
    
    # If not in Lambda or no RDS configured, return as-is
    if not os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or "sqlite" in database_url:
        return database_url
    
    # Get RDS credentials from Secrets Manager
    credentials = get_rds_credentials()
    if not credentials:
        print("Warning: No RDS credentials found, using DATABASE_URL as-is")
        return database_url
    
    print(f"Retrieved credentials: username={credentials.get('username', 'N/A')}, password_length={len(credentials.get('password', ''))}")
    
    # Extract components from DATABASE_URL
    import re
    print(f"Original DATABASE_URL: {database_url}")
    match = re.search(r'postgresql\+asyncpg://[^@]*@([^:/]+):?(\d*)', database_url)
    if not match:
        print(f"Error: Could not parse DATABASE_URL: {database_url}")
        return database_url
    
    host = match.group(1)
    port = match.group(2) or "5432"
    
    # Build connection URL with credentials (URL encode special characters)
    username = credentials.get('username', 'cassidy')
    password = credentials.get('password', '')
    
    # URL encode the password to handle special characters
    encoded_username = urllib.parse.quote(username, safe='')
    encoded_password = urllib.parse.quote(password, safe='')
    
    final_url = f"postgresql+asyncpg://{encoded_username}:{encoded_password}@{host}:{port}/cassidy"
    
    print(f"Database config: host={host}, port={port}, user={username}")
    print(f"Database URL length: {len(final_url)}")
    print(f"Encoded password length: {len(encoded_password)}")
    
    # For debugging - show the URL structure without exposing password
    debug_url = f"postgresql+asyncpg://{username}:{'*' * len(password)}@{host}:{port}/cassidy"
    print(f"URL structure: {debug_url}")
    
    # Check for special characters
    special_chars = ['=', '@', ':', '/', '?', '#', '[', ']', '!', '$', '&', "'", '(', ')', '*', '+', ',', ';']
    has_special = any(c in password for c in special_chars)
    print(f"Password contains special chars: {has_special}")
    
    return final_url