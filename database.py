import sqlite3
import json


def get_db():
    # 🔥 Use a new DB name to force fresh creation on Render
    conn = sqlite3.connect("chatbot_v2.db")
    conn.row_factory = sqlite3.Row
    return conn


# 🔥 NEW: Seed from JSON
def seed_from_json(cursor):
    try:
        with open("seed_data.json", "r") as f:
            data = json.load(f)
    except:
        print("⚠️ seed_data.json not found")
        return

    # Prevent duplicate seeding
    cursor.execute("SELECT COUNT(*) as count FROM intents")
    if cursor.fetchone()["count"] > 0:
        print("ℹ️ DB already seeded")
        return

    for item in data["intents"]:
        intent = item["intent"]
        answer = item["answer"]

        cursor.execute(
            "INSERT INTO intents (intent, answer) VALUES (?, ?)",
            (intent, answer)
        )

        for pattern in item["patterns"]:
            cursor.execute(
                "INSERT INTO patterns (pattern, intent) VALUES (?, ?)",
                (pattern.lower(), intent)
            )

    print("✅ Seed data inserted")


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # --------- ADMINS ---------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    # --------- INTENTS ---------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intent TEXT,
            answer TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------- PATTERNS ---------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT,
            intent TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------- COURSE FEES ---------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS course_fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT,
            fee_amount REAL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------- PENDING QUERIES ---------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            session_id TEXT DEFAULT 'default',
            status TEXT DEFAULT 'pending',
            admin_answer TEXT,
            frequency INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------- CONVERSATION LOG ---------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            user_message TEXT,
            bot_response TEXT,
            intent_matched TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 🔥 NEW: Seed initial chatbot data
    seed_from_json(cursor)

    conn.commit()
    conn.close()

    print("✅ SQLite DB initialized successfully")