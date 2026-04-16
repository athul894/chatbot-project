import re
from database import get_db


# ─────────────────────────────────────────────
# 🏫 COLLEGE TOPIC FILTER
# ─────────────────────────────────────────────
COLLEGE_KEYWORDS = {
    "admission", "admissions", "apply", "application", "enrollment", "enroll",
    "fee", "fees", "cost", "charges", "payment", "tuition",
    "course", "courses", "program", "programs", "branch", "branches", "department",
    "cse", "ece", "mech", "civil", "me", "ce", "bca", "mca", "mba", "mtech", "btech",
    "hostel", "accommodation", "dormitory", "room", "mess",
    "placement", "placements", "job", "jobs", "recruit", "campus", "package",
    "scholarship", "scholarships", "aid", "waiver",
    "library", "books", "reading",
    "timing", "timings", "schedule", "hours", "time",
    "contact", "phone", "address", "email", "office",
    "faculty", "professor", "teacher", "staff",
    "exam", "exams", "examination", "result", "results",
    "college", "university", "institute",
    "transport", "bus", "canteen", "lab", "labs",
    "sports", "club", "clubs", "activity", "activities", "event", "events",
}

# 🔥 STOPWORDS (NEW FIX)
STOPWORDS = {"who", "is", "the", "what", "where", "when", "a", "an", "of"}


def is_college_related(text):
    tokens = set(re.sub(r"[^\w\s]", " ", text.lower()).split())
    return bool(tokens & COLLEGE_KEYWORDS)


def is_valid_query(text):
    return len(text.strip()) >= 3


# ─────────────────────────────────────────────
# 🔍 FEE LOOKUP
# ─────────────────────────────────────────────
def lookup_fee(user_input):
    clean = re.sub(r"[^\w\s]", " ", user_input.lower())
    tokens = set(clean.split())

    fee_triggers = {"fee", "fees", "cost", "charges", "tuition", "price"}
    if not (tokens & fee_triggers):
        return None

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT course_name, fee_amount, description FROM course_fees")
    courses = cursor.fetchall()
    cursor.close()
    db.close()

    for row in courses:
        if row["course_name"].lower() in clean:
            desc = f" ({row['description']})" if row["description"] else ""
            return f"The annual fee for {row['course_name']}{desc} is ₹{int(row['fee_amount']):,}/- per year."

    # fallback: show all fees
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT course_name, fee_amount FROM course_fees ORDER BY course_name")
    all_fees = cursor.fetchall()
    cursor.close()
    db.close()

    if all_fees:
        lines = "\n".join(
            f"• {r['course_name']}: ₹{int(r['fee_amount']):,}/year"
            for r in all_fees
        )
        return f"Here are the annual fees for all programs:\n{lines}"

    return None


# ─────────────────────────────────────────────
# 🔍 FIND RESPONSE (UPDATED FIX)
# ─────────────────────────────────────────────
def find_response(user_input):
    clean = re.sub(r"[^\w\s]", " ", user_input.lower()).strip()

    # 🔥 remove stopwords
    tokens = {t for t in clean.split() if t not in STOPWORDS}

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT p.pattern, i.answer
        FROM patterns p
        JOIN intents i ON p.intent = i.intent
    """)

    rows = cursor.fetchall()
    cursor.close()
    db.close()

    best_answer = None
    best_score = 0

    def normalise(word):
        for suffix in ("tions", "tion", "ments", "ment", "ings", "ing", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                return word[:-len(suffix)]
        return word

    norm_tokens = {normalise(t) for t in tokens}

    for row in rows:
        pattern = re.sub(r"[^\w\s]", " ", row["pattern"].lower()).strip()

        # 🔥 remove stopwords from pattern
        pattern_tokens = {t for t in pattern.split() if t not in STOPWORDS}

        if not pattern_tokens:
            continue

        norm_pattern = {normalise(t) for t in pattern_tokens}

        # 🔥 exact match (strong match)
        if norm_pattern == norm_tokens:
            return row["answer"]

        overlap = len(norm_pattern & norm_tokens)
        score = overlap / len(norm_pattern)

        if score > best_score:
            best_score = score
            best_answer = row["answer"]

    # 🔥 stricter threshold
    if best_score >= 0.6:
        return best_answer

    return None


# ─────────────────────────────────────────────
# 💾 SAVE UNKNOWN QUERY
# ─────────────────────────────────────────────
def save_pending_query(query, session_id="default"):
    clean = query.strip().lower()
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT id FROM pending_queries WHERE query=? AND status='pending'",
        (clean,)
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            "UPDATE pending_queries SET frequency = frequency + 1 WHERE id=?",
            (existing["id"],)
        )
    else:
        cursor.execute(
            "INSERT INTO pending_queries (query, session_id) VALUES (?, ?)",
            (clean, session_id)
        )

    db.commit()
    cursor.close()
    db.close()


# ─────────────────────────────────────────────
# 🤖 MAIN BOT FUNCTION
# ─────────────────────────────────────────────
def get_bot_response(user_input, session_id="default"):
    user_input = user_input.strip()

    if not user_input:
        return {"response": "Please type a message.", "pending": False}

    # Step 1: Fee lookup
    fee_answer = lookup_fee(user_input)
    if fee_answer:
        return {"response": fee_answer, "pending": False}

    # Step 2: Knowledge base
    answer = find_response(user_input)
    if answer:
        return {"response": answer, "pending": False}

    # Step 3: Off-topic filter
    if not is_college_related(user_input):
        return {
            "response": "I can only answer questions related to our college — admissions, courses, fees, hostel, placements, and more.",
            "pending": False
        }

    # Step 4: Save unknown query
    if is_valid_query(user_input):
        save_pending_query(user_input, session_id)
        return {
            "response": "I don't have an answer for that yet. Your question has been sent for admin review.",
            "pending": True
        }

    # Step 5: vague query
    return {
        "response": "Please ask a more specific question.",
        "pending": False
    }