import mysql.connector
from mysql.connector import pooling
import bcrypt

# ── Update credentials here ───────────────────
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Athul@Cyber26!",
    "database": "chatbot_db",
    "autocommit": False
}
# ─────────────────────────────────────────────

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="chatbot_pool",
            pool_size=10,
            **DB_CONFIG
        )
    return _pool


def get_db():
    return get_pool().get_connection()


def init_db():
    """
    Creates ALL required tables and seeds default data.
    Safe to call multiple times (uses IF NOT EXISTS + INSERT IGNORE).
    """
    db = get_db()
    cursor = db.cursor()

    # ── Admins table ───────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )
    """)

    # ── Intents table ──────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            intent VARCHAR(255) UNIQUE NOT NULL,
            answer TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Patterns table ─────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pattern VARCHAR(500) UNIQUE NOT NULL,
            intent VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Course fees table ──────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS course_fees (
            id INT AUTO_INCREMENT PRIMARY KEY,
            course_name VARCHAR(100) UNIQUE NOT NULL,
            fee_amount DECIMAL(10,2) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Pending queries table ──────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_queries (
            id INT AUTO_INCREMENT PRIMARY KEY,
            query TEXT NOT NULL,
            session_id VARCHAR(100) DEFAULT 'default',
            status ENUM('pending','resolved','dismissed') DEFAULT 'pending',
            admin_answer TEXT,
            frequency INT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)

    # ── Conversation log table ─────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id VARCHAR(100),
            user_message TEXT,
            bot_response TEXT,
            intent_matched VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Seed default admin account ─────────────────────────────────
    hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt())
    cursor.execute(
        "INSERT IGNORE INTO admins (username, password) VALUES (%s, %s)",
        ("admin", hashed.decode())
    )

    # ── Seed default intents ───────────────────────────────────────
    default_intents = [
        ("greeting",    "Hello! Welcome to the College Enquiry System. I can help you with admissions, fees, courses, faculty, and more. What would you like to know?"),
        ("farewell",    "Goodbye! Feel free to come back anytime you have questions. Have a great day!"),
        ("admission",   "Admissions are open for the academic year 2024-25. You can apply online at our college website or visit the admissions office between 9 AM and 4 PM on weekdays. Required documents: 10th & 12th marksheets, transfer certificate, and passport photos."),
        ("courses",     "We offer:\n• B.Tech – CSE, ECE, ME, CE (4 years)\n• BCA (3 years)\n• MCA (2 years)\n• MBA (2 years)\n• M.Tech – CSE, ECE (2 years)\nVisit the academic section for detailed syllabi."),
        ("timing",      "College timings: Monday–Friday 9:00 AM to 4:30 PM. Saturday 9:00 AM to 1:00 PM. Library: 8:30 AM to 6:00 PM (weekdays)."),
        ("hostel",      "Hostel facilities are available for boys and girls. Separate blocks with 24/7 security, WiFi, mess, and laundry. Monthly: ₹8,000 (with food) / ₹4,500 (without food). Contact: hostel@college.edu"),
        ("placement",   "Our placement cell has a strong track record. Last year 92% of eligible students were placed. Top recruiters: TCS, Infosys, Wipro, Accenture. Average package: ₹5.2 LPA. Highest: ₹18 LPA."),
        ("contact",     "📞 Phone: +91-XXXXXXXXXX\n📧 Email: info@college.edu\n📍 Address: College Road, City – 500001\nOffice hours: 9 AM – 5 PM (Mon–Sat)"),
        ("scholarship", "We offer merit-based and need-based scholarships. Students scoring above 90% in 12th get up to 50% fee waiver. Government scholarships (SC/ST/OBC/EBC) are also processed. Visit the scholarship cell for details."),
        ("library",     "Our library has 50,000+ books, 200+ journals, and e-resources. Hours: 8:30 AM – 6:00 PM (Mon–Fri). Students may borrow up to 3 books for 14 days. Online catalog available on the college portal."),
        ("transport",   "College buses operate on 12 routes covering major areas of the city. Monthly bus pass: ₹1,200. Contact the transport office for route details and timings."),
        ("exam",        "End-semester exams are held in November and April. Internal assessments are conducted monthly. Exam schedules are posted on the college notice board and student portal 30 days in advance."),
        ("faculty",     "Our faculty comprises highly qualified professors, many with PhDs from reputed institutions. The student-to-faculty ratio is 20:1. Faculty profiles are available on the college website."),
        ("canteen",     "The college canteen is open 8:00 AM to 5:00 PM on weekdays. It serves a variety of vegetarian and non-vegetarian meals at subsidised prices. There is also a separate snacks counter."),
    ]

    cursor.executemany(
        "INSERT IGNORE INTO intents (intent, answer) VALUES (%s, %s)",
        default_intents
    )

    # ── Seed default patterns ──────────────────────────────────────
    default_patterns = [
        # Greeting
        ("hello", "greeting"), ("hi", "greeting"), ("hey", "greeting"),
        ("good morning", "greeting"), ("good afternoon", "greeting"), ("good evening", "greeting"),
        # Farewell
        ("bye", "farewell"), ("goodbye", "farewell"), ("see you", "farewell"),
        ("thank you", "farewell"), ("thanks", "farewell"),
        # Admission
        ("admission", "admission"), ("apply", "admission"), ("how to join", "admission"),
        ("enrollment", "admission"), ("how to apply", "admission"), ("joining process", "admission"),
        # Courses — added singular + common variants
        ("courses", "courses"), ("programs", "courses"), ("branches", "courses"),
        ("what courses", "courses"), ("available courses", "courses"), ("departments", "courses"),
        ("department", "courses"), ("branch", "courses"), ("program", "courses"),
        ("course", "courses"), ("what branch", "courses"), ("which course", "courses"),
        # Timing
        ("timing", "timing"), ("timings", "timing"), ("working hours", "timing"),
        ("college time", "timing"), ("schedule", "timing"), ("when does college open", "timing"),
        # Hostel
        ("hostel", "hostel"), ("accommodation", "hostel"), ("dormitory", "hostel"),
        ("stay", "hostel"), ("room", "hostel"), ("mess", "hostel"),
        # Placement
        ("placement", "placement"), ("placements", "placement"), ("campus recruitment", "placement"),
        ("job", "placement"), ("package", "placement"), ("companies", "placement"),
        # Contact
        ("contact", "contact"), ("phone", "contact"), ("address", "contact"),
        ("email", "contact"), ("how to reach", "contact"), ("location", "contact"),
        # Scholarship
        ("scholarship", "scholarship"), ("scholarships", "scholarship"),
        ("financial aid", "scholarship"), ("fee waiver", "scholarship"),
        # Library
        ("library", "library"), ("books", "library"), ("reading room", "library"),
        # Transport
        ("transport", "transport"), ("bus", "transport"), ("college bus", "transport"),
        # Exam
        ("exam", "exam"), ("exams", "exam"), ("examination", "exam"),
        ("result", "exam"), ("results", "exam"), ("test", "exam"),
        # Faculty
        ("faculty", "faculty"), ("professor", "faculty"), ("teachers", "faculty"),
        ("staff", "faculty"), ("lecturer", "faculty"),
        # Canteen
        ("canteen", "canteen"), ("food", "canteen"), ("cafeteria", "canteen"),
    ]

    cursor.executemany(
        "INSERT IGNORE INTO patterns (pattern, intent) VALUES (%s, %s)",
        default_patterns
    )

    # ── Seed course fees ───────────────────────────────────────────
    default_fees = [
        ("CSE",    95000, "Computer Science & Engineering"),
        ("ECE",    90000, "Electronics & Communication Engineering"),
        ("ME",     85000, "Mechanical Engineering"),
        ("CE",     85000, "Civil Engineering"),
        ("BCA",    60000, "Bachelor of Computer Applications"),
        ("MCA",    75000, "Master of Computer Applications"),
        ("MBA",    80000, "Master of Business Administration"),
        ("M.Tech", 70000, "Master of Technology"),
    ]

    cursor.executemany(
        "INSERT IGNORE INTO course_fees (course_name, fee_amount, description) VALUES (%s, %s, %s)",
        default_fees
    )

    db.commit()
    cursor.close()
    db.close()
    print("✅ Database initialised successfully!")