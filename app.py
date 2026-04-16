import os

from flask import Flask, render_template, request, jsonify, session, redirect
from chatbot import get_bot_response
from database import get_db, init_db
import bcrypt

app = Flask(__name__)
app.secret_key = "supersecretkey123"


# ─────────────────────────────────────────────
# 🔐 GLOBAL ADMIN PROTECTION
# ─────────────────────────────────────────────
@app.before_request
def protect_admin_routes():
    if request.path.startswith("/admin"):
        if not session.get("admin"):
            return redirect("/login")


# ─────────────────────────────────────────────
# 👤 CHATBOT ROUTES
# ─────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html", is_admin=session.get("admin"))


@app.route("/get", methods=["POST"])
def chatbot_response():
    data = request.json
    user_input = data.get("message", "")
    session_id = data.get("session_id", "default")
    response = get_bot_response(user_input, session_id)
    return jsonify(response)


# ─────────────────────────────────────────────
# 🔐 LOGIN SYSTEM
# ─────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin"):
        return redirect("/admin")

    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM admins WHERE username=?", (username,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user:
            stored_password = user["password"]

            # Handle both string and bytes safely
            if isinstance(stored_password, str):
                stored_password = stored_password.encode("utf-8")

            if bcrypt.checkpw(password.encode("utf-8"), stored_password):
                session["admin"] = True
                return redirect("/admin")
            else:
                error = "Invalid username or password"
        else:
            error = "Invalid username or password"

    return render_template("login.html", error=error)


# ─────────────────────────────────────────────
# 🚪 LOGOUT
# ─────────────────────────────────────────────
@app.route("/logout")
def logout():
    if not session.get("admin"):
        return redirect("/login")
    session.clear()
    return redirect("/")


# ─────────────────────────────────────────────
# 🔐 ADMIN PANEL
# ─────────────────────────────────────────────
@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/login")
    return render_template("admin.html")


# ─────────────────────────────────────────────
# 🔐 ADMIN APIs
# ─────────────────────────────────────────────
@app.route("/admin/answer", methods=["POST"])
def add_answer():
    if not session.get("admin"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    data = request.json
    query_id = data.get("query_id")
    answer = data.get("answer", "").strip()
    intent = data.get("intent", "").strip()
    pattern = data.get("pattern", "").strip()

    if not answer or not query_id:
        return jsonify({"success": False, "error": "Missing fields"})

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM pending_queries WHERE id=?", (query_id,))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        db.close()
        return jsonify({"success": False, "error": "Query not found"})

    use_intent = intent if intent else f"intent_{query_id}"
    use_pattern = pattern if pattern else row["query"].lower().strip()

    cursor.execute(
        "INSERT OR IGNORE INTO intents (intent, answer) VALUES (?, ?)",
        (use_intent, answer)
    )

    cursor.execute(
        "INSERT OR IGNORE INTO patterns (pattern, intent) VALUES (?, ?)",
        (use_pattern, use_intent)
    )

    cursor.execute(
        "UPDATE pending_queries SET status='resolved', admin_answer=? WHERE id=?",
        (answer, query_id)
    )

    db.commit()
    cursor.close()
    db.close()

    return jsonify({"success": True})


# ─────────────────────────────────────────────
# ✏️ UPDATE INTENT (FIXED)
# ─────────────────────────────────────────────
@app.route("/admin/update-intent", methods=["POST"])
def update_intent():
    if not session.get("admin"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json()

    intent = data.get("intent")
    answer = data.get("answer")
    new_pattern = data.get("pattern")

    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute(
            "UPDATE intents SET answer=? WHERE intent=?",
            (answer, intent)
        )

        if new_pattern and new_pattern.strip():
            cursor.execute(
                "INSERT OR IGNORE INTO patterns (pattern, intent) VALUES (?, ?)",
                (new_pattern.strip().lower(), intent)
            )

        db.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)})

    finally:
        cursor.close()
        db.close()


# ─────────────────────────────────────────────
# 🗑️ DELETE INTENT (FIXED)
# ─────────────────────────────────────────────
@app.route("/admin/delete-intent/<intent>", methods=["DELETE"])
def delete_intent(intent):
    if not session.get("admin"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("DELETE FROM patterns WHERE intent=?", (intent,))
        cursor.execute("DELETE FROM intents WHERE intent=?", (intent,))

        db.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)})

    finally:
        cursor.close()
        db.close()


# ─────────────────────────────────────────────
# 📋 GET QUERIES
# ─────────────────────────────────────────────
@app.route("/admin/queries")
def get_queries():
    if not session.get("admin"):
        return redirect("/login")


    status = request.args.get("status", "pending")

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM pending_queries WHERE status=? ORDER BY created_at DESC",
        (status,)
    )

    queries = cursor.fetchall()
    queries = [dict(q) for q in queries]    

    cursor.close()
    db.close()

    for q in queries:
        if q["created_at"] is not None:
            q["created_at"] = str(q["created_at"])

    return jsonify(queries)


# ─────────────────────────────────────────────
# 🗑️ DELETE QUERY
# ─────────────────────────────────────────────
@app.route("/admin/delete/<int:query_id>", methods=["DELETE"])
def delete_query(query_id):
    if not session.get("admin"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM pending_queries WHERE id=?", (query_id,))
    db.commit()

    cursor.close()
    db.close()

    return jsonify({"success": True})


# ─────────────────────────────────────────────
# 📊 STATS
# ─────────────────────────────────────────────
@app.route("/admin/stats")
def get_stats():
    if not session.get("admin"):
        return redirect("/login")
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM pending_queries WHERE status='pending'")
    pending = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM pending_queries WHERE status='resolved'")
    resolved = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM intents")
    intents = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM patterns")
    patterns = cursor.fetchone()["count"]

    cursor.close()
    db.close()

    return jsonify({
        "pending": pending,
        "resolved": resolved,
        "intents": intents,
        "patterns": patterns
    })


# ─────────────────────────────────────────────
# 📚 KNOWLEDGE BASE
# ─────────────────────────────────────────────
@app.route("/admin/knowledge")
def get_knowledge():
    if not session.get("admin"):
        return redirect("/login")
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT 
            i.id,
            i.intent,
            i.answer,
            i.created_at,
            GROUP_CONCAT(p.pattern SEPARATOR '|||') AS patterns
        FROM intents i
        LEFT JOIN patterns p ON p.intent = i.intent
        GROUP BY i.id
        ORDER BY i.created_at DESC
    """)

    data = cursor.fetchall()

    for row in data:
        row["patterns"] = row["patterns"].split("|||") if row["patterns"] else []
        if row["created_at"] is not None:
            row["created_at"] = str(row["created_at"])

    cursor.close()
    db.close()

    return jsonify(data)


# ─────────────────────────────────────────────
# 🛠 INIT DATABASE
# ─────────────────────────────────────────────
@app.route("/init-db")
def initialize_db():
    if not session.get("admin"):
        return redirect("/login")   
    init_db()
    return "✅ Database initialised successfully!"

@app.route("/create-admin")
def create_admin():
    if not session.get("admin"):
        return redirect("/login")
    import bcrypt
    db = get_db()
    cursor = db.cursor()

    password = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt())

    cursor.execute(
        "INSERT INTO admins (username, password) VALUES (?, ?)",
        ("admin", password)
    )

    db.commit()
    db.close()

    return "Admin created"

# ─────────────────────────────────────────────
# 🚀 RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)