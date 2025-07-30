#!/usr/bin/env python3
"""
Database Backup and Restore Script
Creates backups of databases and restores from backups.
Supports both local SQLite and production PostgreSQL.
"""

import os
import subprocess
import asyncio
import sys
import boto3
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DatabaseBackup:
    def __init__(self, backup_dir: str = "/Users/cyan/code/cassidy-claudecode/backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        
    def parse_database_url(self, database_url: str) -> dict:
        """Parse database URL into components"""
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'username': parsed.username,
            'password': parsed.password,
            'scheme': parsed.scheme
        }
    
    def get_production_database_url(self) -> str:
        """Get production database URL from AWS"""
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
            
            # Get secret ARN from CloudFormation resources
            resources = cf.describe_stack_resources(StackName='CassidyBackendStack')
            secret_arn = None
            
            for resource in resources['StackResources']:
                if resource['ResourceType'] == 'AWS::SecretsManager::Secret':
                    secret_arn = resource['PhysicalResourceId']
                    break
            
            if not secret_arn:
                raise Exception("Database secret not found in CloudFormation resources")
            
            # Get credentials from Secrets Manager
            secrets_client = boto3.client('secretsmanager')
            response = secrets_client.get_secret_value(SecretId=secret_arn)
            credentials = json.loads(response['SecretString'])
            
            # Build connection URL (sync postgresql for pg_dump)
            username = credentials['username']
            password = credentials['password']
            
            # URL encode special characters
            import urllib.parse
            encoded_username = urllib.parse.quote(username, safe='')
            encoded_password = urllib.parse.quote(password, safe='')
            
            production_url = f"postgresql://{encoded_username}:{encoded_password}@{db_endpoint}:5432/cassidy"
            
            print(f"Production DB: {username}@{db_endpoint}:5432/cassidy")
            return production_url
            
        except Exception as e:
            raise Exception(f"Failed to get production database URL: {e}")
        
    async def backup_postgres(self, database_url: str) -> str:
        """Create a PostgreSQL backup using pg_dump"""
        db_info = self.parse_database_url(database_url)
        
        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"cassidy_backup_{timestamp}.sql"
        backup_path = self.backup_dir / backup_filename
        
        # Set environment variables for pg_dump
        env = os.environ.copy()
        if db_info['password']:
            env['PGPASSWORD'] = db_info['password']
            
        # Build pg_dump command
        cmd = [
            'pg_dump',
            '-h', str(db_info['host']),
            '-p', str(db_info['port']),
            '-U', db_info['username'],
            '-d', db_info['database'],
            '--verbose',
            '--clean',
            '--if-exists',
            '--no-owner',
            '--no-privileges',
            '-f', str(backup_path)
        ]
        
        print(f"Creating backup: {backup_filename}")
        print(f"Command: {' '.join(cmd[:7])} ... [credentials hidden]")
        
        try:
            # Run pg_dump
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                backup_size = backup_path.stat().st_size
                print(f"✓ Backup created successfully: {backup_filename}")
                print(f"  Size: {backup_size / 1024 / 1024:.2f} MB")
                return str(backup_path)
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"pg_dump failed: {error_msg}")
                
        except FileNotFoundError:
            raise Exception("pg_dump not found. Please install PostgreSQL client tools.")
        except Exception as e:
            if backup_path.exists():
                backup_path.unlink()  # Remove incomplete backup
            raise e
    
    async def restore_postgres(self, backup_file: str, database_url: str) -> bool:
        """Restore a PostgreSQL database from backup"""
        db_info = self.parse_database_url(database_url)
        backup_path = Path(backup_file)
        
        if not backup_path.exists():
            raise Exception(f"Backup file not found: {backup_file}")
        
        # Set environment variables for psql
        env = os.environ.copy()
        if db_info['password']:
            env['PGPASSWORD'] = db_info['password']
            
        # Build psql command
        cmd = [
            'psql',
            '-h', str(db_info['host']),
            '-p', str(db_info['port']),
            '-U', db_info['username'],
            '-d', db_info['database'],
            '-f', str(backup_path),
            '--quiet'
        ]
        
        print(f"Restoring from backup: {backup_path.name}")
        print(f"Command: {' '.join(cmd[:7])} ... [credentials hidden]")
        
        try:
            # Run psql
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                print(f"✓ Database restored successfully from: {backup_path.name}")
                return True
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"psql restore failed: {error_msg}")
                
        except FileNotFoundError:
            raise Exception("psql not found. Please install PostgreSQL client tools.")
        except Exception as e:
            raise e
            
    async def backup_sqlite(self, database_url: str) -> str:
        """Create a SQLite backup"""
        # Extract database path from URL
        if database_url.startswith('sqlite:///'):
            db_path = database_url[10:]  # Remove 'sqlite:///'
        else:
            db_path = database_url.replace('sqlite://', '')
            
        source_path = Path(db_path)
        if not source_path.exists():
            raise Exception(f"SQLite database not found: {source_path}")
            
        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"cassidy_backup_{timestamp}.db"
        backup_path = self.backup_dir / backup_filename
        
        print(f"Creating SQLite backup: {backup_filename}")
        
        # Copy the database file
        import shutil
        shutil.copy2(source_path, backup_path)
        
        backup_size = backup_path.stat().st_size
        print(f"✓ Backup created successfully: {backup_filename}")
        print(f"  Size: {backup_size / 1024 / 1024:.2f} MB")
        
        return str(backup_path)
    
    async def restore_sqlite(self, backup_file: str, database_url: str) -> bool:
        """Restore a SQLite database from backup"""
        # Extract database path from URL
        if database_url.startswith('sqlite:///'):
            db_path = database_url[10:]  # Remove 'sqlite:///'
        else:
            db_path = database_url.replace('sqlite://', '')
            
        backup_path = Path(backup_file)
        target_path = Path(db_path)
        
        if not backup_path.exists():
            raise Exception(f"Backup file not found: {backup_file}")
        
        print(f"Restoring SQLite database: {target_path.name}")
        
        # Copy the backup file to the target location
        import shutil
        shutil.copy2(backup_path, target_path)
        
        print(f"✓ Database restored successfully from: {backup_path.name}")
        return True
        
    def cleanup_old_backups(self, keep_days: int = 30):
        """Remove backups older than specified days"""
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
        
        removed_count = 0
        for backup_file in self.backup_dir.glob("cassidy_backup_*"):
            if backup_file.stat().st_mtime < cutoff_time:
                backup_file.unlink()
                removed_count += 1
                print(f"Removed old backup: {backup_file.name}")
                
        if removed_count > 0:
            print(f"Cleaned up {removed_count} old backup(s)")
        else:
            print("No old backups to clean up")
            
    async def backup_database(self, database_url: str) -> str:
        """Create a backup of the specified database"""
        if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
            return await self.backup_postgres(database_url)
        elif database_url.startswith('sqlite://'):
            return await self.backup_sqlite(database_url)
        else:
            raise Exception(f"Unsupported database type: {database_url}")
    
    async def restore_database(self, backup_file: str, database_url: str) -> bool:
        """Restore a database from backup"""
        if database_url.startswith('postgresql://') or database_url.startswith('postgres://'):
            return await self.restore_postgres(backup_file, database_url)
        elif database_url.startswith('sqlite://'):
            return await self.restore_sqlite(backup_file, database_url)
        else:
            raise Exception(f"Unsupported database type: {database_url}")
            
    async def run_backup(self, database_url: str = None, cleanup: bool = True):
        """Run the backup process"""
        if not database_url:
            # Try to get production database URL
            try:
                database_url = self.get_production_database_url()
                print("Using production database URL")
            except Exception as e:
                print(f"Could not get production URL: {e}")
                # Fall back to local database
                database_url = os.getenv('DATABASE_URL', 'sqlite:///./cassidy.db')
                print("Using local database URL")
                
        print("Database Backup Script")
        print("=" * 60)
        print(f"Backup directory: {self.backup_dir}")
        print(f"Database URL: {database_url.split('@')[0]}@[hidden]" if '@' in database_url else database_url)
        print("=" * 60)
        
        try:
            backup_path = await self.backup_database(database_url)
            
            if cleanup:
                print("\nCleaning up old backups...")
                self.cleanup_old_backups()
                
            print(f"\n✓ Backup completed successfully: {backup_path}")
            return backup_path
            
        except Exception as e:
            print(f"✗ Backup failed: {str(e)}")
            raise


async def main():
    """Main function"""
    backup = DatabaseBackup()
    
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python backup_db.py backup [database_url]           # Create backup")
        print("  python backup_db.py restore <backup_file> [database_url]  # Restore from backup")
        print("  python backup_db.py list                            # List available backups")
        print("")
        print("Examples:")
        print("  python backup_db.py backup                          # Backup production DB")
        print("  python backup_db.py backup sqlite:///./local.db     # Backup specific DB")
        print("  python backup_db.py restore backup.sql             # Restore to production")
        print("  python backup_db.py list                            # Show available backups")
        return
        
    command = sys.argv[1]
    
    if command == "backup":
        database_url = sys.argv[2] if len(sys.argv) > 2 else None
        await backup.run_backup(database_url)
        
    elif command == "restore":
        if len(sys.argv) < 3:
            print("Error: backup file required for restore")
            print("Usage: python backup_db.py restore <backup_file> [database_url]")
            return
            
        backup_file = sys.argv[2]
        database_url = None
        
        if len(sys.argv) > 3:
            database_url = sys.argv[3]
        else:
            # Try to get production database URL for restore
            try:
                database_url = backup.get_production_database_url()
                print("Using production database URL for restore")
            except Exception as e:
                print(f"Could not get production URL: {e}")
                database_url = os.getenv('DATABASE_URL', 'sqlite:///./cassidy.db')
                print("Using local database URL for restore")
        
        print("\n⚠️  WARNING: This will overwrite the target database!")
        confirm = input("Are you sure you want to restore? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Restore cancelled")
            return
            
        try:
            await backup.restore_database(backup_file, database_url)
        except Exception as e:
            print(f"✗ Restore failed: {str(e)}")
            
    elif command == "list":
        print("Available backups:")
        print("=" * 50)
        backup_files = list(backup.backup_dir.glob("cassidy_backup_*"))
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not backup_files:
            print("No backups found")
        else:
            for i, backup_file in enumerate(backup_files, 1):
                size_mb = backup_file.stat().st_size / 1024 / 1024
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
                print(f"{i:2d}. {backup_file.name:30s} {size_mb:6.1f}MB  {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
                
    else:
        print(f"Unknown command: {command}")
        print("Available commands: backup, restore, list")


if __name__ == "__main__":
    asyncio.run(main())