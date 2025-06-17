#!/usr/bin/env python3
"""Test database connection with AWS RDS"""
import asyncio
import os
import json
import boto3
import asyncpg
import ssl


async def test_connection():
    """Test RDS connection with credentials from Secrets Manager"""
    
    # Simulate Lambda environment variables
    database_url = os.environ.get("DATABASE_URL", "")
    db_secret_arn = os.environ.get("DB_SECRET_ARN", "")
    
    print(f"DATABASE_URL: {database_url}")
    print(f"DB_SECRET_ARN: {db_secret_arn}")
    
    if not database_url or not db_secret_arn:
        print("ERROR: Missing environment variables")
        return
    
    try:
        # Get credentials from Secrets Manager
        print("\nFetching credentials from Secrets Manager...")
        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
        secret_response = secrets_client.get_secret_value(SecretId=db_secret_arn)
        secret_data = json.loads(secret_response['SecretString'])
        
        username = secret_data['username']
        password = secret_data['password']
        print(f"Username: {username}")
        
        # Extract host from DATABASE_URL
        import re
        match = re.search(r'postgresql\+asyncpg://[^@]*@([^:/]+)', database_url)
        if not match:
            print("ERROR: Could not parse host from DATABASE_URL")
            return
            
        host = match.group(1)
        print(f"Host: {host}")
        
        # Test connection without SSL first
        print("\nTesting connection WITHOUT SSL...")
        try:
            conn = await asyncpg.connect(
                host=host,
                port=5432,
                user=username,
                password=password,
                database='cassidy',
                timeout=10
            )
            print("SUCCESS: Connected without SSL")
            await conn.close()
        except Exception as e:
            print(f"FAILED without SSL: {type(e).__name__}: {e}")
        
        # Test connection with SSL
        print("\nTesting connection WITH SSL...")
        try:
            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            conn = await asyncpg.connect(
                host=host,
                port=5432,
                user=username,
                password=password,
                database='cassidy',
                ssl=ssl_context,
                timeout=10
            )
            print("SUCCESS: Connected with SSL")
            
            # Test a simple query
            version = await conn.fetchval('SELECT version()')
            print(f"PostgreSQL version: {version}")
            
            await conn.close()
        except Exception as e:
            print(f"FAILED with SSL: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Testing RDS PostgreSQL connection...")
    print("=" * 50)
    asyncio.run(test_connection())