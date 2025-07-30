#!/usr/bin/env python3
"""
Journal Import CLI Helper
Shows commands to import journals one by one
"""

import subprocess
import sys
from pathlib import Path

def show_import_status():
    """Show current import status"""
    result = subprocess.run([
        sys.executable, "check_db_status.py"
    ], capture_output=True, text=True)
    
    print(result.stdout)
    
    # Extract counts
    lines = result.stdout.split('\n')
    journal_count = 0
    task_count = 0
    
    for line in lines:
        if 'Journal Entries (finalized):' in line:
            journal_count = int(line.split(':')[1].strip())
        elif 'Tasks Created:' in line:
            task_count = int(line.split(':')[1].strip())
    
    return journal_count, task_count

def main():
    print("🚀 JOURNAL IMPORT CLI")
    print("=" * 50)
    
    # Show current status
    journal_count, task_count = show_import_status()
    
    # List available files
    import_dir = Path("/Users/cyan/code/cassidy-claudecode/import")
    journal_files = sorted(import_dir.glob("*.txt"))
    
    print(f"\n📊 PROGRESS: {journal_count}/7 journal entries imported")
    print(f"✅ Tasks created: {task_count}")
    
    print(f"\n📁 IMPORT COMMANDS:")
    print("Run these one by one:")
    print()
    
    for i, file_path in enumerate(journal_files, 1):
        status = "✅" if i <= journal_count else "⏳"
        print(f"{status} {i}. uv run python import_single_journal.py {file_path.name}")
    
    print()
    print("📝 USAGE:")
    print("  • Run each command one by one")
    print("  • Watch the detailed progress output")
    print("  • Check status: uv run python import_cli.py")
    print("  • If import fails, re-run the same command")
    
    if journal_count < 7:
        next_file = journal_files[journal_count].name
        print(f"\n🎯 NEXT TO IMPORT:")
        print(f"   uv run python import_single_journal.py {next_file}")

if __name__ == "__main__":
    main()