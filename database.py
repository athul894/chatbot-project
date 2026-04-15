import sqlite3

def get_db():
    conn = sqlite3.connect("chatbot.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # --------- CREATE TABLES ---------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intents (
            id INTEGER PRIMARY KEY,
            intent TEXT,
            answer TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY,
            pattern TEXT,
            intent TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS course_fees (
            id INTEGER PRIMARY KEY,
            course_name TEXT,
            fee_amount REAL,
            description TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            session_id TEXT DEFAULT 'default',
            status TEXT DEFAULT 'pending',
            admin_answer TEXT,
            frequency INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            user_message TEXT,
            bot_response TEXT,
            intent_matched TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

    print("✅ SQLite DB ready")