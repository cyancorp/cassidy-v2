#!/usr/bin/env python3
"""
Update Flutter app API URL configuration
Updates the mobile app's API configuration with the current backend URL
"""

import os
import re
import subprocess
import sys

def get_backend_api_url():
    """Get the current backend API URL from CloudFormation"""
    try:
        result = subprocess.run([
            'aws', 'cloudformation', 'describe-stacks',
            '--stack-name', 'CassidyBackendStack',
            '--query', 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue',
            '--output', 'text'
        ], capture_output=True, text=True, check=True)
        
        api_url = result.stdout.strip()
        if api_url and api_url != 'None':
            return f"{api_url}/api/v1"
        else:
            print("❌ Could not get API URL from CloudFormation stack")
            return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Error getting API URL: {e}")
        return None

def update_flutter_config(new_api_url):
    """Update the Flutter app configuration with new API URL"""
    
    config_file = '../mobile_flutter/lib/config/app_config.dart'
    
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        return False
    
    try:
        # Read current config
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Update the API URL
        updated_content = re.sub(
            r"static const String apiBaseUrl = '[^']*';",
            f"static const String apiBaseUrl = '{new_api_url}';",
            content
        )
        
        if updated_content == content:
            print("⚠️  No API URL found to update in config file")
            return False
        
        # Write updated config
        with open(config_file, 'w') as f:
            f.write(updated_content)
        
        print(f"✅ Updated Flutter config: {new_api_url}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating config file: {e}")
        return False

def update_flutter_readme(new_api_url):
    """Update the Flutter README with new API URL"""
    
    readme_file = '../mobile_flutter/README.md'
    
    if not os.path.exists(readme_file):
        print(f"❌ README not found: {readme_file}")
        return False
    
    try:
        # Read current README
        with open(readme_file, 'r') as f:
            content = f.read()
        
        # Update the API URL in README
        updated_content = re.sub(
            r"- \*\*Base URL\*\*: `[^`]*`",
            f"- **Base URL**: `{new_api_url}`",
            content
        )
        
        if updated_content != content:
            # Write updated README
            with open(readme_file, 'w') as f:
                f.write(updated_content)
            print("✅ Updated Flutter README")
            return True
        else:
            print("⚠️  No API URL found to update in README")
            return False
        
    except Exception as e:
        print(f"❌ Error updating README: {e}")
        return False

def main():
    print("🔄 Updating Flutter app API configuration...")
    
    # Check if we're in the infrastructure directory
    if not os.path.exists('app.py'):
        print("❌ Must run from infrastructure directory")
        sys.exit(1)
    
    # Get current API URL
    api_url = get_backend_api_url()
    if not api_url:
        sys.exit(1)
    
    print(f"📡 Current API URL: {api_url}")
    
    # Update Flutter configuration
    config_updated = update_flutter_config(api_url)
    readme_updated = update_flutter_readme(api_url)
    
    if config_updated or readme_updated:
        print(f"\n🎉 Flutter app updated successfully!")
        print(f"📱 API URL: {api_url}")
        print(f"📁 Config file: mobile_flutter/lib/config/app_config.dart")
        print(f"📄 README file: mobile_flutter/README.md")
        print(f"\n💡 To test the mobile app:")
        print(f"   cd ../mobile_flutter")
        print(f"   flutter run")
    else:
        print("⚠️  No updates were made")

if __name__ == "__main__":
    main()