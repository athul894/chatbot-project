import re
from database import get_db
from difflib import SequenceMatcher


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
    "faculty", "professor", "teacher", "staff", "hod", "head",
    "exam", "exams", "examination", "result", "results",
    "college", "university", "institute",
    "transport", "bus", "canteen", "lab", "labs",
    "sports", "club", "clubs", "activity", "activities", "event", "events",
    "alumni", "research", "cafeteria", "gym", "extracurricular",
    # Extended — legitimately college-related, ensures they go to admin not rejected
    "wifi", "internet", "network",
    "students", "student", "strength", "intake",
    "principal", "director", "chancellor", "management",
    "accreditation", "naac", "nba", "ranking", "rank",
    "infrastructure", "building", "facilities",
    "certificate", "degree", "diploma",
    "internship", "internships", "project", "projects",
    "attendance", "syllabus", "curriculum",
}

# Words that carry no discriminative meaning for matching
STOPWORDS = {
    "who", "is", "the", "what", "where", "when", "a", "an", "of",
    "for", "do", "you", "me", "tell", "about", "in", "my", "i",
    "can", "how", "many", "any", "are", "there", "have", "has",
    "does", "this", "that", "it", "will", "your", "get", "give",
    "please", "want", "need", "know", "find", "show", "let",
}


def is_college_related(text):
    """Return True if at least one token is a known college keyword."""
    tokens = set(re.sub(r"[^\w\s]", " ", text.lower()).split())
    return bool(tokens & COLLEGE_KEYWORDS)


def is_valid_query(text):
    """Reject single-character or empty input."""
    return len(text.strip()) >= 3


# ─────────────────────────────────────────────
# 🔤 TEXT HELPERS
# ─────────────────────────────────────────────
def clean_text(text):
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


def normalize(word):
    """Strip common suffixes so 'placements' and 'placement' both reduce to 'placement'."""
    for suffix in ("tions", "tion", "ments", "ment", "ings", "ing", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def tokenize(text):
    """Clean, remove stopwords, and normalize each token."""
    raw = {t for t in clean_text(text).split() if t not in STOPWORDS}
    return {normalize(t) for t in raw}


# ─────────────────────────────────────────────
# 🔍 FEE LOOKUP  (dedicated — runs before pattern matching)
# ─────────────────────────────────────────────
def lookup_fee(user_input):
    """
    Handles fee-related queries directly from the course_fees table.
    Only activates when the query contains a fee-trigger word.
    Returns None if not a fee query, so the bot can continue to pattern matching.
    """
    clean = clean_text(user_input)
    tokens = set(clean.split())

    fee_triggers = {"fee", "fees", "cost", "charges", "tuition", "price", "amount"}
    if not (tokens & fee_triggers):
        return None

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT course_name, fee_amount, description FROM course_fees")
    courses = cursor.fetchall()
    cursor.close()
    db.close()

    # Try to match a specific course mentioned in the query
    for row in courses:
        if row["course_name"].lower() in clean:
            desc = f" ({row['description']})" if row["description"] else ""
            return f"The annual fee for {row['course_name']}{desc} is ₹{int(row['fee_amount']):,}/- per year."

    # No specific course mentioned — list all fees
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT course_name, fee_amount FROM course_fees ORDER BY course_name")
    all_fees = cursor.fetchall()
    cursor.close()
    db.close()

    if all_fees:
        lines = "\n".join(
            f"• {r['course_name']}: ₹{int(r['fee_amount']):,}/year" for r in all_fees
        )
        return f"Here are the annual fees for all programs:\n{lines}"

    return None


# ─────────────────────────────────────────────
# 🔎 PATTERN MATCHING
# ─────────────────────────────────────────────
def _score_pattern(query_norm_tokens, pattern_raw):
    """
    Score how well a stored pattern matches the user's query.

    Scoring approach — F1 over token sets:
      precision = overlap / len(pattern_tokens)   (how much of pattern appears in query)
      recall    = overlap / len(query_tokens)      (how much of query is covered by pattern)
      F1        = harmonic mean of precision & recall

    Why F1 instead of just precision?
      Pure precision lets "student research" match "students" with score 0.5
      because 1 of 2 pattern tokens matches. F1 also penalises low recall, meaning
      a pattern must not just appear IN the query — the query must also be well
      covered BY the pattern.

    Keyword boost (+0.15):
      Applied only when:
        - At least one overlapping token is a college keyword, AND
        - Either overlap >= 2 (strong multi-keyword evidence), OR
          the pattern is a single token (exact topic word match like "hostel")
      This prevents single-keyword coincidences from getting boosted.

    Returns 0 immediately if no token overlap (avoids SequenceMatcher inflation
    from shared stopwords like "what is the").
    """
    pattern = clean_text(pattern_raw)
    pt_raw = {t for t in pattern.split() if t not in STOPWORDS}
    if not pt_raw:
        return 0

    npt = {normalize(t) for t in pt_raw}

    # Pass 1: exact normalized match
    if npt == query_norm_tokens:
        return 1.0

    overlap = len(npt & query_norm_tokens)
    if overlap == 0:
        return 0  # No shared tokens — skip; avoids stopword-inflated similarity scores

    # Pass 2: F1 score
    precision = overlap / len(npt)
    recall = overlap / len(query_norm_tokens)
    f1 = 2 * precision * recall / (precision + recall)

    # Keyword boost — guarded to prevent spurious single-token matches
    kw_overlap = len(npt & query_norm_tokens & COLLEGE_KEYWORDS)
    if kw_overlap > 0 and (overlap >= 2 or len(npt) == 1):
        f1 += 0.15

    return f1


def find_response(user_input):
    """
    Query the intents+patterns DB and return the best matching answer.
    Returns None if no pattern scores at or above the confidence threshold.

    Threshold = 0.70:
      - High enough to reject partial/coincidental matches
      - Low enough to catch natural paraphrasing (e.g. "tell me about placements"
        matches "placement details")
    """
    norm_tokens = tokenize(user_input)
    if not norm_tokens:
        return None

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

    for row in rows:
        score = _score_pattern(norm_tokens, row["pattern"])
        if score > best_score:
            best_score = score
            best_answer = row["answer"]

    THRESHOLD = 0.70
    return best_answer if best_score >= THRESHOLD else None


# ─────────────────────────────────────────────
# 💾 SAVE UNKNOWN QUERY
# ─────────────────────────────────────────────
def save_pending_query(query, session_id="default"):
    """
    Persist a college-related question the bot couldn't answer.
    Deduplicates: increments frequency if the same pending query already exists.
    """
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
    """
    Decision pipeline (order matters):

      1. Empty input          → ask user to type something
      2. Fee query            → lookup_fee() → course_fees table (runs before pattern
                                matching so fee questions always get exact fee data)
      3. Pattern match        → find_response() → intents+patterns DB
      4. Off-topic            → politely reject (NEVER forwarded to admin)
      5. College-related,
         no answer found      → save_pending_query() → admin review
      6. Too vague            → ask for more detail
    """
    user_input = user_input.strip()

    # ── 1. Empty guard ──────────────────────────────────────────
    if not user_input:
        return {"response": "Please type a message.", "pending": False}

    # ── 2. Fee lookup ───────────────────────────────────────────
    fee_answer = lookup_fee(user_input)
    if fee_answer:
        return {"response": fee_answer, "pending": False}

    # ── 3. Pattern / intent match ───────────────────────────────
    answer = find_response(user_input)
    if answer:
        return {"response": answer, "pending": False}

    # ── 4. Reject off-topic (never forward these to admin) ──────
    if not is_college_related(user_input):
        return {
            "response": (
                "I can only answer questions related to our college — "
                "admissions, courses, fees, hostel, placements, and more."
            ),
            "pending": False,
        }

    # ── 5. College-related but no answer → forward to admin ─────
    if is_valid_query(user_input):
        save_pending_query(user_input, session_id)
        return {
            "response": (
                "I don't have an answer for that yet. "
                "Your question has been forwarded to the admin for review. "
                "Please check back later!"
            ),
            "pending": True,
        }

    # ── 6. Too vague ────────────────────────────────────────────
    return {
        "response": "Please ask a more specific question.",
        "pending": False,
    }