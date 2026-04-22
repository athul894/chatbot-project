import re
import nltk
from database import get_db

# ─────────────────────────────────────────────
# 📦 NLTK SETUP — downloads run once on first launch
# ─────────────────────────────────────────────
nltk.download("punkt",     quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("stopwords", quiet=True)
nltk.download("wordnet",   quiet=True)
nltk.download("omw-1.4",   quiet=True)

from nltk.tokenize import word_tokenize
from nltk.corpus   import stopwords
from nltk.stem     import WordNetLemmatizer

lemmatizer = WordNetLemmatizer()
STOP_WORDS = set(stopwords.words("english"))


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
    "wifi", "internet", "network",
    "students", "student", "strength", "intake",
    "principal", "director", "chancellor", "management",
    "accreditation", "naac", "nba", "ranking", "rank",
    "infrastructure", "building", "facilities",
    "certificate", "degree", "diploma",
    "internship", "internships", "project", "projects",
    "attendance", "syllabus", "curriculum",
}


# ─────────────────────────────────────────────
# 🔤 NLP PREPROCESSING  (NLTK pipeline)
# ─────────────────────────────────────────────
def clean_text(text):
    """Remove punctuation and convert to lowercase."""
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


def tokenize(text):
    """
    Full NLP preprocessing pipeline using NLTK:

      Step 1 — clean_text()     : remove punctuation, lowercase
      Step 2 — word_tokenize()  : split into tokens (handles contractions etc.)
      Step 3 — stopword removal : drop common filler words (NLTK English stopwords)
      Step 4 — lemmatize()      : reduce each word to its dictionary base form
                                  e.g. "placements" → "placement"
                                       "timings"    → "timing"
                                       "fees"       → "fee"

    Returns a set of cleaned, lemmatized tokens.
    """
    cleaned = clean_text(text)

    # Step 2 — NLTK tokenization
    tokens = word_tokenize(cleaned)

    # Step 3 — NLTK stopword removal
    tokens = [t for t in tokens if t not in STOP_WORDS]

    # Step 4 — NLTK lemmatization
    tokens = [lemmatizer.lemmatize(t) for t in tokens]

    return set(tokens)


def is_college_related(text):
    """
    Returns True if the query contains at least one college-related keyword.
    Used to decide whether an unanswered query should be forwarded to admin
    or rejected as off-topic.
    """
    tokens = set(word_tokenize(clean_text(text)))
    return bool(tokens & COLLEGE_KEYWORDS)


def is_valid_query(text):
    """Reject inputs that are too short to be meaningful."""
    return len(text.strip()) >= 3


# ─────────────────────────────────────────────
# 🔍 FEE LOOKUP  (runs before pattern matching)
# ─────────────────────────────────────────────
def lookup_fee(user_input):
    """
    Dedicated handler for fee-related queries.
    Queries the course_fees table directly so fee data is always accurate
    and not dependent on pattern matching.

    Only activates when the input contains a fee-trigger word.
    Returns None otherwise so the bot continues to pattern matching.
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

    # Match a specific course name mentioned in the query
    for row in courses:
        if row["course_name"].lower() in clean:
            desc = f" ({row['description']})" if row["description"] else ""
            return (
                f"The annual fee for {row['course_name']}{desc} "
                f"is ₹{int(row['fee_amount']):,}/- per year."
            )

    # No specific course found — list all fees
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
# 🔎 PATTERN MATCHING
# ─────────────────────────────────────────────
def _score_pattern(query_tokens, pattern_raw):
    """
    Scores how well a stored pattern matches the user's query
    using F1 over lemmatized token sets.

    F1 score (harmonic mean of precision and recall):
      precision = overlap / pattern tokens  — how much of pattern is in query
      recall    = overlap / query tokens    — how much of query is in pattern

    Using F1 instead of precision alone prevents partial matches from
    scoring too high (e.g. "student research" matching "students").

    Keyword boost (+0.15):
      Applied when a college keyword appears in the overlap AND
      either overlap >= 2 tokens OR the pattern is a single token.
      This rewards strong domain-specific matches without boosting
      accidental single-word overlaps.

    Returns 0 immediately if there is no token overlap at all,
    avoiding any inflation from shared stopwords.
    """
    # Tokenize and lemmatize the stored pattern the same way as the query
    pattern_tokens = tokenize(pattern_raw)
    if not pattern_tokens:
        return 0

    # Pass 1 — exact normalized match
    if pattern_tokens == query_tokens:
        return 1.0

    overlap = len(pattern_tokens & query_tokens)
    if overlap == 0:
        return 0

    # Pass 2 — F1 score
    precision = overlap / len(pattern_tokens)
    recall    = overlap / len(query_tokens)
    f1 = 2 * precision * recall / (precision + recall)

    # Keyword boost
    kw_overlap = len(pattern_tokens & query_tokens & COLLEGE_KEYWORDS)
    if kw_overlap > 0 and (overlap >= 2 or len(pattern_tokens) == 1):
        f1 += 0.15

    return f1


def find_response(user_input):
    """
    Scores every pattern in the database against the user query
    and returns the answer of the best-matching intent.

    Confidence threshold = 0.70:
      Scores below this are treated as no match — the query is
      either rejected (off-topic) or forwarded to admin.
    """
    query_tokens = tokenize(user_input)
    if not query_tokens:
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
    best_score  = 0

    for row in rows:
        score = _score_pattern(query_tokens, row["pattern"])
        if score > best_score:
            best_score  = score
            best_answer = row["answer"]

    THRESHOLD = 0.70
    return best_answer if best_score >= THRESHOLD else None


# ─────────────────────────────────────────────
# 💾 SAVE UNKNOWN QUERY
# ─────────────────────────────────────────────
def save_pending_query(query, session_id="default"):
    """
    Saves a college-related unanswered query for admin review.
    If the same query is already pending, increments its frequency
    counter instead of inserting a duplicate.
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
    Main decision pipeline — order matters:

      1. Empty input check
         → prompt user to type something

      2. Fee lookup  (lookup_fee)
         → query course_fees table directly
         → runs BEFORE pattern matching so fee queries always
           return accurate structured data

      3. Pattern matching  (find_response)
         → NLTK-preprocessed F1 scoring against intents+patterns DB
         → returns answer if confidence >= 0.70

      4. Off-topic rejection  (is_college_related)
         → queries with no college keyword are rejected here
         → NEVER forwarded to admin

      5. Forward to admin  (save_pending_query)
         → college-related query with no matching answer
         → stored in pending_queries table for admin review

      6. Too vague
         → fallback for very short inputs that passed earlier guards
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

    # ── 4. Reject off-topic queries ─────────────────────────────
    if not is_college_related(user_input):
        return {
            "response": (
                "I can only answer questions related to our college — "
                "admissions, courses, fees, hostel, placements, and more."
            ),
            "pending": False,
        }

    # ── 5. College-related but unanswered → forward to admin ────
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