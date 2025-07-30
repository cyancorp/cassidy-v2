#!/usr/bin/env python3
"""
Push user data from local SQLite to production PostgreSQL and create backup
"""

import asyncio
import sys
import os
import json
import boto3
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db, init_db
from app.models.user import UserDB
from app.models.session import JournalEntryDB, JournalDraftDB, ChatSessionDB, ChatMessageDB
from app.models.task import TaskDB
from sqlalchemy import select, text, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


def log_step(step: str, status: str = "🔧"):
    """Log a step with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{status} [{timestamp}] {step}")


def get_rds_credentials() -> Dict[str, Any]:
    """Get RDS credentials from AWS Secrets Manager"""
    
    # First try to get the secret ARN from CloudFormation
    try:
        cf = boto3.client('cloudformation')
        response = cf.describe_stacks(StackName='CassidyBackendStack')
        outputs = response['Stacks'][0]['Outputs']
        
        # Look for database secret ARN in outputs or resources
        log_step("Looking for database secret ARN in CloudFormation...")
        
        # Get resources to find the secret
        resources = cf.describe_stack_resources(StackName='CassidyBackendStack')
        secret_arn = None
        
        for resource in resources['StackResources']:
            if resource['ResourceType'] == 'AWS::SecretsManager::Secret':
                secret_arn = resource['PhysicalResourceId']
                break
        
        if not secret_arn:
            raise Exception("Database secret not found in CloudFormation resources")
        
        log_step(f"Found secret ARN: {secret_arn}")
        
    except Exception as e:
        log_step(f"Error getting secret ARN from CloudFormation: {e}", "❌")
        raise
    
    # Get credentials from Secrets Manager
    try:
        secrets_client = boto3.client('secretsmanager')
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        credentials = json.loads(response['SecretString'])
        
        log_step(f"Retrieved credentials for user: {credentials.get('username', 'unknown')}")
        return credentials
        
    except Exception as e:
        log_step(f"Failed to get RDS credentials: {e}", "❌")
        raise


def get_production_database_url() -> str:
    """Get production database URL"""
    
    try:
        # Get database endpoint from CloudFormation
        cf = boto3.client('cloudformation')
        response = cf.describe_stacks(StackName='CassidyBackendStack')
        outputs = response['Stacks'][0]['Outputs']
        
        db_endpoint = None
        for output in outputs:
            if output['OutputKey'] == 'DatabaseEndpoint':
                db_endpoint = output['OutputValue']
                break
        
        if not db_endpoint:
            raise Exception("Database endpoint not found in CloudFormation outputs")
        
        # Get credentials
        credentials = get_rds_credentials()
        
        # Build connection URL
        username = credentials['username']
        password = credentials['password']
        
        # URL encode special characters
        import urllib.parse
        encoded_username = urllib.parse.quote(username, safe='')
        encoded_password = urllib.parse.quote(password, safe='')
        
        production_url = f"postgresql+asyncpg://{encoded_username}:{encoded_password}@{db_endpoint}:5432/cassidy"
        
        log_step(f"Production DB: {username}@{db_endpoint}:5432/cassidy")
        return production_url
        
    except Exception as e:
        log_step(f"Failed to get production database URL: {e}", "❌")
        raise


async def export_user_data(user_id: str) -> Dict[str, Any]:
    """Export all data for a specific user from local database"""
    
    log_step("Exporting user data from local database...")
    
    # Use local SQLite database
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./cassidy.db"
    await init_db()
    
    export_data = {}
    
    async for db in get_db():
        # Export user
        result = await db.execute(select(UserDB).where(UserDB.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise Exception(f"User {user_id} not found")
        
        export_data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'password_hash': user.password_hash,
            'is_verified': user.is_verified,
            'is_active': user.is_active,
            'created_at': user.created_at,
            'updated_at': user.updated_at
        }
        
        # Export user preferences
        result = await db.execute(text('SELECT * FROM user_preferences WHERE user_id = :user_id'), {'user_id': user_id})
        prefs = result.fetchone()
        if prefs:
            export_data['user_preferences'] = dict(prefs._mapping)
        
        # Export journal entries
        result = await db.execute(select(JournalEntryDB).where(JournalEntryDB.user_id == user_id))
        journal_entries = result.scalars().all()
        export_data['journal_entries'] = []
        for entry in journal_entries:
            export_data['journal_entries'].append({
                'id': entry.id,
                'user_id': entry.user_id,
                'session_id': entry.session_id,
                'title': entry.title,
                'raw_text': entry.raw_text,
                'structured_data': entry.structured_data,
                'created_at': entry.created_at,
                'updated_at': entry.updated_at
            })
        
        # Export tasks
        result = await db.execute(select(TaskDB).where(TaskDB.user_id == user_id))
        tasks = result.scalars().all()
        export_data['tasks'] = []
        for task in tasks:
            export_data['tasks'].append({
                'id': task.id,
                'user_id': task.user_id,
                'title': task.title,
                'description': task.description,
                'priority': task.priority,
                'is_completed': task.is_completed,
                'due_date': task.due_date,
                'completed_at': task.completed_at,
                'created_at': task.created_at,
                'updated_at': task.updated_at,
                'source_session_id': task.source_session_id
            })
        
        # Export chat sessions
        result = await db.execute(select(ChatSessionDB).where(ChatSessionDB.user_id == user_id))
        sessions = result.scalars().all()
        export_data['chat_sessions'] = []
        for session in sessions:
            export_data['chat_sessions'].append({
                'id': session.id,
                'user_id': session.user_id,
                'conversation_type': session.conversation_type,
                'is_active': session.is_active,
                'metadata': session.session_metadata,
                'created_at': session.created_at,
                'updated_at': session.updated_at
            })
        
        # Export chat messages
        result = await db.execute(text('SELECT * FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE user_id = :user_id)'), {'user_id': user_id})
        messages = result.fetchall()
        export_data['chat_messages'] = []
        for msg in messages:
            export_data['chat_messages'].append(dict(msg._mapping))
        
        # Export journal drafts
        result = await db.execute(select(JournalDraftDB).where(JournalDraftDB.user_id == user_id))
        drafts = result.scalars().all()
        export_data['journal_drafts'] = []
        for draft in drafts:
            export_data['journal_drafts'].append({
                'id': draft.id,
                'session_id': draft.session_id,
                'user_id': draft.user_id,
                'draft_data': draft.draft_data,
                'is_finalized': draft.is_finalized,
                'created_at': draft.created_at,
                'updated_at': draft.updated_at
            })
        
        break
    
    log_step(f"Exported data for user {export_data['user']['username']}:")
    log_step(f"  - Journal entries: {len(export_data['journal_entries'])}")
    log_step(f"  - Tasks: {len(export_data['tasks'])}")
    log_step(f"  - Chat sessions: {len(export_data['chat_sessions'])}")
    log_step(f"  - Chat messages: {len(export_data['chat_messages'])}")
    log_step(f"  - Journal drafts: {len(export_data['journal_drafts'])}")
    
    return export_data


async def import_to_production(export_data: Dict[str, Any]):
    """Import data to production database"""
    
    log_step("Importing data to production database...")
    
    # Set up production database connection
    production_url = get_production_database_url()
    os.environ["DATABASE_URL"] = production_url
    
    # Initialize production database
    await init_db()
    
    async for db in get_db():
        # Check if user already exists
        result = await db.execute(select(UserDB).where(UserDB.id == export_data['user']['id']))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            log_step(f"User {export_data['user']['username']} already exists in production, updating...", "⚠️")
            # Update existing user
            for key, value in export_data['user'].items():
                if key not in ['id']:  # Don't update ID
                    setattr(existing_user, key, value)
        else:
            log_step(f"Creating new user {export_data['user']['username']} in production...")
            # Create new user
            new_user = UserDB(**export_data['user'])
            db.add(new_user)
        
        # Import user preferences
        if 'user_preferences' in export_data:
            # Delete existing preferences
            await db.execute(text('DELETE FROM user_preferences WHERE user_id = :user_id'), {'user_id': export_data['user']['id']})
            # Insert new preferences
            await db.execute(text('''
                INSERT INTO user_preferences (user_id, purpose_statement, long_term_goals, known_challenges, preferred_feedback_style, personal_glossary, created_at, updated_at)
                VALUES (:user_id, :purpose_statement, :long_term_goals, :known_challenges, :preferred_feedback_style, :personal_glossary, :created_at, :updated_at)
            '''), export_data['user_preferences'])
        
        # Import journal entries
        await db.execute(text('DELETE FROM journal_entries WHERE user_id = :user_id'), {'user_id': export_data['user']['id']})
        for entry in export_data['journal_entries']:
            await db.execute(text('''
                INSERT INTO journal_entries (id, user_id, session_id, title, raw_text, structured_data, created_at, updated_at)
                VALUES (:id, :user_id, :session_id, :title, :raw_text, :structured_data, :created_at, :updated_at)
            '''), entry)
        
        # Import tasks
        await db.execute(text('DELETE FROM tasks WHERE user_id = :user_id'), {'user_id': export_data['user']['id']})
        for task in export_data['tasks']:
            await db.execute(text('''
                INSERT INTO tasks (id, user_id, title, description, priority, is_completed, due_date, completed_at, created_at, updated_at, source_session_id)
                VALUES (:id, :user_id, :title, :description, :priority, :is_completed, :due_date, :completed_at, :created_at, :updated_at, :source_session_id)
            '''), task)
        
        # Import chat sessions
        await db.execute(text('DELETE FROM chat_sessions WHERE user_id = :user_id'), {'user_id': export_data['user']['id']})
        for session in export_data['chat_sessions']:
            await db.execute(text('''
                INSERT INTO chat_sessions (id, user_id, conversation_type, is_active, metadata, created_at, updated_at)
                VALUES (:id, :user_id, :conversation_type, :is_active, :metadata, :created_at, :updated_at)
            '''), session)
        
        # Import chat messages
        await db.execute(text('DELETE FROM chat_messages WHERE session_id IN (SELECT id FROM chat_sessions WHERE user_id = :user_id)'), {'user_id': export_data['user']['id']})
        for msg in export_data['chat_messages']:
            await db.execute(text('''
                INSERT INTO chat_messages (id, session_id, role, content, created_at, metadata)
                VALUES (:id, :session_id, :role, :content, :created_at, :metadata)
            '''), msg)
        
        # Import journal drafts
        await db.execute(text('DELETE FROM journal_drafts WHERE user_id = :user_id'), {'user_id': export_data['user']['id']})
        for draft in export_data['journal_drafts']:
            await db.execute(text('''
                INSERT INTO journal_drafts (id, session_id, user_id, draft_data, is_finalized, created_at, updated_at)
                VALUES (:id, :session_id, :user_id, :draft_data, :is_finalized, :created_at, :updated_at)
            '''), draft)
        
        await db.commit()
        
        log_step("✅ Data successfully imported to production!")
        break


async def create_production_backup():
    """Create a backup of the production database"""
    
    log_step("Creating production database backup...")
    
    try:
        # Get database details
        cf = boto3.client('cloudformation')
        response = cf.describe_stacks(StackName='CassidyBackendStack')
        
        # Find database identifier
        resources = cf.describe_stack_resources(StackName='CassidyBackendStack')
        db_identifier = None
        
        for resource in resources['StackResources']:
            if resource['ResourceType'] == 'AWS::RDS::DBInstance':
                db_identifier = resource['PhysicalResourceId']
                break
        
        if not db_identifier:
            raise Exception("Database instance not found in CloudFormation resources")
        
        # Create snapshot
        rds = boto3.client('rds')
        snapshot_id = f"cassidy-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        log_step(f"Creating snapshot: {snapshot_id}")
        
        response = rds.create_db_snapshot(
            DBSnapshotIdentifier=snapshot_id,
            DBInstanceIdentifier=db_identifier
        )
        
        log_step(f"✅ Backup snapshot initiated: {snapshot_id}")
        log_step("Note: Snapshot creation will continue in background")
        
        return snapshot_id
        
    except Exception as e:
        log_step(f"Failed to create backup: {e}", "❌")
        raise


async def main():
    """Main function"""
    print("\n🚀 PUSH DATA TO PRODUCTION")
    print("=" * 60)
    
    # User ID to export (jg2950)
    user_id = "df6f0fb0-3039-4e73-8852-8ced8e1d88b1"
    
    try:
        # Step 1: Export data from local database
        export_data = await export_user_data(user_id)
        
        # Step 2: Import to production
        await import_to_production(export_data)
        
        # Step 3: Create backup
        snapshot_id = await create_production_backup()
        
        print(f"\n✅ SUCCESS!")
        print("=" * 60)
        print(f"User data pushed to production successfully")
        print(f"Backup snapshot: {snapshot_id}")
        print(f"Production database contains:")
        print(f"  - User: {export_data['user']['username']}")
        print(f"  - Journal entries: {len(export_data['journal_entries'])}")
        print(f"  - Tasks: {len(export_data['tasks'])}")
        print(f"  - Chat sessions: {len(export_data['chat_sessions'])}")
        print(f"  - Chat messages: {len(export_data['chat_messages'])}")
        print(f"  - Journal drafts: {len(export_data['journal_drafts'])}")
        
    except Exception as e:
        log_step(f"Error: {str(e)}", "❌")
        print(f"\n❌ FAILED: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)