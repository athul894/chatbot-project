import sqlite3
import csv

conn = sqlite3.connect("chatbot.db")
cursor = conn.cursor()

# ---------- CREATE TABLES ----------

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
    id INTEGER PRIMARY KEY,
    query TEXT
)
""")

# ---------- INSERT FUNCTION ----------

def insert_csv(file, table, columns):
    with open(file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            values = [row[col] for col in columns]
            placeholders = ",".join(["?"] * len(values))
            cursor.execute(
                f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
                values
            )

# ---------- INSERT DATA ----------

insert_csv("intents.csv", "intents", ["id", "intent", "answer", "created_at"])
insert_csv("patterns.csv", "patterns", ["id", "pattern", "intent", "created_at"])
insert_csv("course_fees.csv", "course_fees", ["id", "course_name", "fee_amount", "description", "created_at"])
insert_csv("pending_queries.csv", "pending_queries", ["id", "query"])

conn.commit()
conn.close()

print("✅ Migration completed successfully!")