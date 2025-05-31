#!/usr/bin/env python3
"""
Script to organize data files to the correct structure.
- Move user data from data/user/user_123_*.json to data/user_123/
- Move user data from data/user/default_user_*.json to data/user/default_user/
- Clean up any inconsistent or unnecessary files
"""

import os
import json
import shutil
from pathlib import Path

# Set up paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
USER_DIR = DATA_DIR / "user"
SESSIONS_DIR = DATA_DIR / "sessions"

def ensure_dir(path):
    """Ensure a directory exists."""
    path.mkdir(parents=True, exist_ok=True)

def copy_file(src, dst):
    """Copy a file, creating parent directories if needed."""
    ensure_dir(dst.parent)
    if src.exists():
        print(f"Copying {src} to {dst}")
        shutil.copy2(src, dst)
        return True
    return False

def delete_file(path):
    """Delete a file if it exists."""
    if path.exists():
        print(f"Deleting {path}")
        path.unlink()
        return True
    return False

def migrate_user_files():
    """Move user files to their correct locations."""
    # Find all user_* files in USER_DIR
    for file_path in USER_DIR.glob("*_*.*"):
        if file_path.name.endswith(".json"):
            parts = file_path.stem.split("_")
            if len(parts) >= 2:
                # Extract the full user ID, not just the first part
                # For example, from "user_123_preferences.json", user_id should be "user_123"
                # Special cases like "test_user_001" need to be handled differently
                
                # Common patterns:
                # user_123_preferences.json -> user_id = "user_123"
                # test_user_001_preferences.json -> user_id = "test_user_001"
                # default_user_template.json -> user_id = "default_user"
                
                if "preferences" in file_path.stem:
                    # For preferences files
                    user_id = file_path.stem.replace("_preferences", "")
                elif "template" in file_path.stem:
                    # For template files
                    user_id = file_path.stem.replace("_template", "")
                else:
                    # Fallback to first part if pattern is unclear
                    user_id = parts[0]
                    print(f"Warning: Using fallback user_id '{user_id}' for {file_path}")
                
                # Create user-specific directory
                user_specific_dir = USER_DIR / user_id
                ensure_dir(user_specific_dir)
                
                # Determine target filename
                if "template" in file_path.stem:
                    target_file = user_specific_dir / "template.json"
                elif "preferences" in file_path.stem:
                    target_file = user_specific_dir / "preferences.json"
                else:
                    # Unknown file type, skip
                    print(f"Skipping unknown file type: {file_path}")
                    continue
                
                # Copy file
                copy_file(file_path, target_file)
                
                # Delete original
                delete_file(file_path)

def migrate_user_directories():
    """Move files from incorrect user directories to the correct ones."""
    # Check for user_123 directory directly under data
    incorrect_user_dir = DATA_DIR / "user_123"
    if incorrect_user_dir.exists() and incorrect_user_dir.is_dir():
        print(f"Found incorrect user directory: {incorrect_user_dir}")
        
        # Create correct user directory
        correct_user_dir = USER_DIR / "user_123"
        ensure_dir(correct_user_dir)
        
        # Migrate each file
        for file_path in incorrect_user_dir.glob("*.json"):
            if "template" in file_path.name:
                target_file = correct_user_dir / "template.json"
                copy_file(file_path, target_file)
                delete_file(file_path)
            elif "preferences" in file_path.name:
                target_file = correct_user_dir / "preferences.json"
                copy_file(file_path, target_file)
                delete_file(file_path)
            else:
                print(f"Skipping unknown file: {file_path}")
        
        # Try to delete the directory now that files should be removed
        try:
            print(f"Removing directory: {incorrect_user_dir}")
            incorrect_user_dir.rmdir()
        except OSError as e:
            print(f"Warning: Could not remove directory {incorrect_user_dir}: {e}")
            print(f"Files remaining: {list(incorrect_user_dir.glob('*'))}")
    
    # Also check any other incorrectly placed user directories
    for user_dir in DATA_DIR.glob("user_*"):
        if user_dir.is_dir() and user_dir != USER_DIR:
            user_id = user_dir.name
            print(f"Found another incorrect user directory: {user_dir}")
            
            # Create correct user directory
            correct_user_dir = USER_DIR / user_id
            ensure_dir(correct_user_dir)
            
            # Migrate each file
            for file_path in user_dir.glob("*.json"):
                if "template" in file_path.name:
                    target_file = correct_user_dir / "template.json"
                    copy_file(file_path, target_file)
                    delete_file(file_path)
                elif "preferences" in file_path.name:
                    target_file = correct_user_dir / "preferences.json"
                    copy_file(file_path, target_file)
                    delete_file(file_path)
                else:
                    print(f"Skipping unknown file: {file_path}")
            
            # Try to delete the directory now that files should be removed
            try:
                print(f"Removing directory: {user_dir}")
                user_dir.rmdir()
            except OSError as e:
                print(f"Warning: Could not remove directory {user_dir}: {e}")
                print(f"Files remaining: {list(user_dir.glob('*'))}")

def clean_session_files():
    """Clean up session files with incorrect naming."""
    # Handle the incorrect "current_chat_id" files
    current_chat_id_file = SESSIONS_DIR / "current_chat_id_structured.json"
    if current_chat_id_file.exists():
        print(f"Found hardcoded session file: {current_chat_id_file}")
        
        # Read the file to get actual session ID
        try:
            with open(current_chat_id_file, 'r') as f:
                data = json.load(f)
            
            # Get the session ID and user ID
            session_id = data.get("session_id", "unknown_session")
            
            # Fix session_id if it's still "current_chat_id"
            if session_id == "current_chat_id":
                # Use timestamp from the file as session ID
                from datetime import datetime
                session_id = f"migrated_{datetime.now().strftime('%Y%m%dT%H%M%SZ')}"
                data["session_id"] = session_id
            
            # Default to user_123 if user_id not present
            user_id = "user_123"
            
            # Create correct filename
            correct_filename = f"{user_id}_{session_id}_structured.json"
            correct_path = SESSIONS_DIR / correct_filename
            
            # Save file with correct name
            with open(correct_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved with correct name: {correct_path}")
            
            # Delete original
            delete_file(current_chat_id_file)
            
        except Exception as e:
            print(f"Error processing {current_chat_id_file}: {e}")

def migrate_data():
    """Main function to migrate all data."""
    print("Starting data migration...")
    
    # Ensure directories exist
    ensure_dir(DATA_DIR)
    ensure_dir(USER_DIR)
    ensure_dir(SESSIONS_DIR)
    
    # Migrate user files from incorrect filenames
    migrate_user_files()
    
    # Migrate files from incorrect directories
    migrate_user_directories()
    
    # Clean session files
    clean_session_files()
    
    print("Data migration complete!")

if __name__ == "__main__":
    migrate_data() 