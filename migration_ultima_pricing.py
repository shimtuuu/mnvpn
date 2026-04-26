#!/usr/bin/env python3
"""
Migration script to add max_devices field to existing database.
Run this ONCE after updating to Ultima VPN pricing model.
"""

import sqlite3
import sys
from config import DB_PATH

def run_migration():
    print(f"⚡ Running migration on {DB_PATH}...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if max_devices column already exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'max_devices' in columns:
            print("✅ Field 'max_devices' already exists - migration skipped")
            return
        
        # Add max_devices column
        cursor.execute("ALTER TABLE users ADD COLUMN max_devices INTEGER DEFAULT 1")
        
        # Sync max_devices with existing device_limit
        cursor.execute("UPDATE users SET max_devices = device_limit WHERE device_limit IS NOT NULL")
        
        conn.commit()
        print("✅ Migration successful! Field 'max_devices' added to users table")
        print("🔄 Synced max_devices with existing device_limit values")
        
    except sqlite3.OperationalError as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
