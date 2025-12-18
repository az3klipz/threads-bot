import sqlite3
import datetime
import os
from .constants import DB_FILE

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Leads Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        status TEXT DEFAULT 'Followed', -- Followed, Messaged, Replied, Unfollowed
        source TEXT DEFAULT 'auto', -- manual, auto (keyword/competitor)
        follow_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_interaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        message_count INTEGER DEFAULT 0,
        notes TEXT
    )
    ''')
    
    # Saved Posts Table Removed
    
    # Interactions Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        type TEXT, -- like, follow, comment, message
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads (id)
    )
    ''')

    # Seen Posts Table (to avoid duplicate interactions)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS seen_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id TEXT UNIQUE,
        type TEXT, -- processed, skipped
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Tasks Queue Table (for future background tasks)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        payload TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Check for source column and add if missing (Migration)
    try:
        cursor.execute('SELECT source FROM leads LIMIT 1')
    except sqlite3.OperationalError:
        print("Migrating DB: Adding source column to leads table...")
        cursor.execute('ALTER TABLE leads ADD COLUMN source TEXT DEFAULT "auto"')
    
    conn.commit()
    conn.close()

def add_lead(username, source="auto"):
    """Adds a new lead or updates timestamp if exists."""
    if not username or username.lower() == "unknown":
        return None
        
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Try to insert with source
        cursor.execute('INSERT OR IGNORE INTO leads (username, source) VALUES (?, ?)', (username, source))
        conn.commit()
        
        cursor.execute('SELECT id FROM leads WHERE username = ?', (username,))
        result = cursor.fetchone()
        
        # If lead existed, we might want to update source if it was auto and now is manual? 
        # For now, let's keep original source.
        
        if result:
             return result['id']
        return None
    except Exception as e:
        print(f"Error adding lead: {e}")
        return None
    finally:
        conn.close()

def log_interaction(username, type, details=""):
    """Logs an interaction for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        lead_id = add_lead(username)
        
        if lead_id:
            cursor.execute('INSERT INTO interactions (lead_id, type, details) VALUES (?, ?, ?)', 
                           (lead_id, type, details))
            
            cursor.execute('UPDATE leads SET last_interaction_date = CURRENT_TIMESTAMP WHERE id = ?', (lead_id,))
            conn.commit()
    except Exception as e:
        print(f"Error logging interaction: {e}")
    finally:
        conn.close()

def get_leads(status_filter=None):
    conn = get_connection()
    cursor = conn.cursor()
    if status_filter:
        cursor.execute('SELECT * FROM leads WHERE status = ? ORDER BY last_interaction_date DESC', (status_filter,))
    else:
        cursor.execute('SELECT * FROM leads ORDER BY last_interaction_date DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_lead_details(username):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM leads WHERE username = ?', (username,))
    lead = cursor.fetchone()
    
    if not lead:
        conn.close()
        return None
        
    cursor.execute('SELECT * FROM interactions WHERE lead_id = ? ORDER BY timestamp DESC', (lead['id'],))
    interactions = cursor.fetchall()
    
    conn.close()
    return dict(lead), [dict(i) for i in interactions]

def update_lead_status(username, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE leads SET status = ? WHERE username = ?', (status, username))
    conn.commit()
    conn.close()

def is_post_seen(post_id):
    if not post_id: return False
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM seen_posts WHERE post_id = ?", (post_id,))
        result = cursor.fetchone()
        return result is not None
    finally:
        conn.close()

def mark_post_seen(post_id, action_type="processed"):
    if not post_id: return
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO seen_posts (post_id, type) VALUES (?, ?)", (post_id, action_type))
        conn.commit()
    except Exception as e:
        print(f"Error marking post seen: {e}")
    finally:
        conn.close()

def is_user_recently_interacted(username, minutes=15):
    if not username: return False
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT i.timestamp 
            FROM interactions i
            JOIN leads l ON i.lead_id = l.id
            WHERE l.username = ?
            ORDER BY i.timestamp DESC
            LIMIT 1
        ''', (username,))
        row = cursor.fetchone()
        
        if row:
            last_time_str = row['timestamp']
            try:
                last_time = datetime.datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
                now = datetime.datetime.utcnow()
                diff = now - last_time
                if diff.total_seconds() < (minutes * 60):
                    return True
            except:
                pass
    except Exception as e:
        print(f"Error checking recent interaction: {e}")
    finally:
        conn.close()
    return False

def add_task(task_type, payload):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO tasks (type, payload) VALUES (?, ?)', (task_type, payload))
        conn.commit()
    except Exception as e:
        print(f"Error adding task: {e}")
    finally:
        conn.close()

def get_pending_tasks():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at ASC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def update_task_status(task_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
        conn.commit()
    except Exception as e:
        print(f"Error updating task status: {e}")
    finally:
        conn.close()

# --- CRM Functions Removed ---

# Initialize on import
if not os.path.exists(DB_FILE):
    init_db()
else:
    init_db()
