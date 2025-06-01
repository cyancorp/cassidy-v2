#!/usr/bin/env python3
"""
Quick SQLite database viewer script
Usage: uv run view_db.py
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = "cassidy.db"

def main():
    if not Path(DB_PATH).exists():
        print(f"Database {DB_PATH} not found!")
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    # Show all tables
    tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
    tables = pd.read_sql_query(tables_query, conn)
    print("📊 Available tables:")
    for table in tables['name']:
        print(f"  • {table}")
    
    print("\n" + "="*50)
    
    # Show sample data from each table
    for table in tables['name']:
        print(f"\n🔍 Sample data from '{table}':")
        try:
            # Get row count
            count_query = f"SELECT COUNT(*) as count FROM {table}"
            count = pd.read_sql_query(count_query, conn)['count'][0]
            print(f"   Total rows: {count}")
            
            # Show first few rows
            sample_query = f"SELECT * FROM {table} LIMIT 3"
            sample_data = pd.read_sql_query(sample_query, conn)
            if not sample_data.empty:
                print(sample_data.to_string(index=False))
            else:
                print("   (empty table)")
        except Exception as e:
            print(f"   Error reading table: {e}")
        print("-" * 30)
    
    conn.close()

if __name__ == "__main__":
    main() 