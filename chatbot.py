import re
from database import get_db
from difflib import SequenceMatcher  # 🔥 NEW 


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
# 🔍 FIND RESPONSE (UPDATED FIX + AUTO-LEARN BOOST)
# ─────────────────────────────────────────────
def find_response(user_input):
    clean = re.sub(r"[^\w\s]", " ", user_input.lower()).strip()
    tokens = {t for t in clean.split() if t not in STOPWORDS}

    def normalize(word):
        for suffix in ("tions", "tion", "ments", "ment", "ings", "ing", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                return word[:-len(suffix)]
        return word

    normalized_tokens = {normalize(t) for t in tokens}

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        SELECT p.pattern, i.answer
        FROM patterns p
        JOIN intents i ON p.intent = i.intent
    """)

    rows = cursor.fetchall()
    cursor.close()
    best_answer = None
    best_score = 0

    norm_tokens = {normalize(t) for t in tokens}
    important_keywords = COLLEGE_KEYWORDS

    # First pass: collect candidates with highest token overlap
    candidates = []
    max_overlap = 0

    for row in rows:
        pattern = re.sub(r"[^\w\s]", " ", row["pattern"].lower()).strip()
        pattern_tokens = {t for t in pattern.split() if t not in STOPWORDS}

        if not pattern_tokens:
            continue

        norm_pattern = {normalize(t) for t in pattern_tokens}

        # exact match
        if norm_pattern == norm_tokens:
            return row["answer"]

        overlap = len(norm_pattern & norm_tokens)
        if overlap > max_overlap:
            max_overlap = overlap
        # 🔥 similarity boost
        similarity = SequenceMatcher(None, clean, pattern).ratio()
        # Combine overlap and similarity with weights (e.g., 0.7 for overlap, 0.3 for similarity)
        score = 0.7 * score + 0.3 * similarity

    # If no overlap, consider all patterns as fallback
    if not candidates:
        candidates = [(row, {normalize(t) for t in {t for t in re.sub(r"[^\w\s]", " ", row["pattern"].lower()).strip().split() if t not in STOPWORDS}}, 
                       re.sub(r"[^\w\s]", " ", row["pattern"].lower()).strip()) for row in rows]

    # Second pass: apply SequenceMatcher only to top candidates
    for row, norm_pattern, pattern in candidates:
        keyword_overlap = len(norm_pattern & norm_tokens & important_keywords)
        overlap = len(norm_pattern & norm_tokens)
        score = overlap / len(norm_pattern) if len(norm_pattern) > 0 else 0

        # 🔥 similarity boost (only for top candidates)
        similarity = SequenceMatcher(None, clean, pattern).ratio()
        score = max(score, similarity)

        # 🔥 boost score if important keyword matches
        if keyword_overlap > 0:
            score += 0.3
        if score > best_score:
            best_score = score
            best_answer = row["answer"]

    # 🔥 slightly smarter thresholding
        # 🔥 slightly smarter thresholding
        if best_score >= 0.6:
            return best_answer

    # Fallback: return best_answer if it meets a lower threshold
    if best_score >= 0.3:
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

    fee_answer = lookup_fee(user_input)
    if fee_answer:
        return {"response": fee_answer, "pending": False}

    answer = find_response(user_input)
    if answer:
        return {"response": answer, "pending": False}

    if not is_college_related(user_input):
        return {
            "response": "I can only answer questions related to our college — admissions, courses, fees, hostel, placements, and more.",
            "pending": False
        }

    if is_valid_query(user_input):
        save_pending_query(user_input, session_id)
        return {
            "response": "I don't have an answer for that yet. Your question has been sent for admin review.",
            "pending": True
        }

    return {
        "response": "Please ask a more specific question.",
        "pending": False
    }