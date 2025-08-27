#!/usr/bin/env python3
"""
Simple Python script to parse messaging.db and echo the most recent chat message.
No external dependencies - uses built-in sqlite3 module.
Simplified for PrivateMessages table only.
"""

import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime

def connect_to_database(db_path="messaging.db", read_only=False):
    """Connect to the SQLite database."""
    try:
        if read_only:
            # Use read-only and immutable mode to prevent WAL/SHM file creation
            # Use absolute path and proper URI format
            import os
            abs_path = os.path.abspath(db_path)
            uri = f"file:{abs_path}?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True)
        else:
            conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def get_most_recent_message(conn, show_details=True):
    """Get the most recent message from PrivateMessages table."""
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM PrivateMessages ORDER BY Timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        
        if row and show_details:
            print("Most recent entry from 'PrivateMessages' table:")
            
            # Display all columns
            for key in row.keys():
                value = row[key]
                
                # Format timestamp if it's the Timestamp column
                if key == 'Timestamp' and isinstance(value, str):
                    print(f"{key}: {value}")
                else:
                    print(f"{key}: {value}")
        
        return row
        
    except sqlite3.Error as e:
        if show_details:
            print(f"Error querying PrivateMessages: {e}")
def get_wal_modtime(wal_path="messaging.db-wal"):
    """Get modification time of WAL file, return None if file doesn't exist."""
    try:
        return os.path.getmtime(wal_path)
    except (OSError, IOError):
        return None

def display_default_message(message_row):
    """Display message in default format: [timestamp][username] message"""
    if message_row:
        timestamp = message_row['Timestamp'] or "unknown time"
        username = message_row['Username'] or "unknown user"
        message = message_row['Message'] or "no message"
        print(f"[{timestamp}][{username}] {message}")

def watch_mode(conn, db_dir):
    """Watch messaging.db-wal for changes and display new messages."""
    wal_path = os.path.join(db_dir, "messaging.db-wal")
    
    
    # Initialize with current latest message timestamp
    latest_message = get_most_recent_message(conn, show_details=False)
    if not latest_message:
        print("No messages found in database")
        return
    
    last_timestamp = latest_message['Timestamp']
    last_wal_modtime = get_wal_modtime(wal_path)  # This returns None if file doesn't exist
    
    # print(f"Watching {wal_path} for changes... (Press Ctrl+C to exit)")
    
    try:
        poll_count = 0
        while True:
            poll_count += 1
            current_wal_modtime = get_wal_modtime(wal_path)
            
            
            # Check if WAL file modification time changed
            # If file didn't exist before but exists now, that's a change
            # If file existed before but doesn't exist now, that's also a change
            # If both are None (file doesn't exist), no change
            if current_wal_modtime != last_wal_modtime:
                last_wal_modtime = current_wal_modtime
                
                # Only check for new messages if WAL file exists
                if current_wal_modtime is not None:
                    # Get latest message
                    current_message = get_most_recent_message(conn, show_details=False)
                    
                    if current_message:
                        current_timestamp = current_message['Timestamp']
                        
                        # String comparison of timestamps
                        if current_timestamp != last_timestamp:
                            last_timestamp = current_timestamp
                            display_default_message(current_message)
            
            time.sleep(5)  # 5-second cooldown for CPU-friendly polling
            
    except KeyboardInterrupt:
        print("\nWatch mode stopped.")
        return None

def main():
    """Main function to parse the database and display the most recent message."""
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description='Parse messaging.db and display the most recent chat message')
    parser.add_argument('directory',
                       help='Directory containing the database file(s)')
    parser.add_argument('-m', '--message', action='store_true',
                       help='Print only the message text')
    parser.add_argument('-i', '--id', action='store_true',
                       help='Print only the message ID')
    parser.add_argument('-t', '--time', action='store_true',
                       help='Print only the timestamp')
    parser.add_argument('-d', '--debug', action='store_true',
                       help='Print detailed information about the message')
    parser.add_argument('-w', '--watch', action='store_true',
                       help='Watch messaging.db-wal for changes and display new messages')
    
    args = parser.parse_args()
    
    # Validate directory exists and is accessible
    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    if not os.access(args.directory, os.R_OK):
        print(f"Error: Directory '{args.directory}' is not readable", file=sys.stderr)
        sys.exit(1)
    
    # Validate mutual exclusivity of watch flag
    if args.watch and any([args.message, args.id, args.time, args.debug]):
        parser.error("--watch/-w cannot be used with other flags")
    
    # Build database path
    db_path = os.path.join(args.directory, "messaging.db")
    
    # Connect to database (watch mode needs write access to see WAL changes)
    conn = connect_to_database(db_path, read_only=False)
    if not conn:
        sys.exit(1)
    
    try:
        if args.watch:
            watch_mode(conn, args.directory)
        else:
            # Get the most recent message
            recent_message = get_most_recent_message(conn, show_details=args.debug)
            
            if not recent_message:
                if args.debug:
                    print("No messages found in the database.")
                sys.exit(1)
            
            # Handle specific field output
            if args.message:
                print(recent_message['Message'])
            elif args.id:
                print(recent_message['Id'])
            elif args.time:
                print(recent_message['Timestamp'])
            elif not args.debug:
                # Default behavior: use the new display function
                display_default_message(recent_message)
        
    except Exception as e:
        if args.debug:
            print(f"An error occurred: {e}")
        sys.exit(1)
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()