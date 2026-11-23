"""CodeAlpha Task 1 - Data Redundancy Removal System (Flask + SQLite)."""
import hashlib, json, os, re, sqlite3
from contextlib import closing
from difflib import SequenceMatcher
from flask import Flask, jsonify, request

EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")
JUNK = {"test", "asdf", "qwerty", "n/a", "na", "none", "null", "xxx", "abc"}
FUZZY = 0.9  # name similarity threshold for near-duplicates
app = Flask(__name__)
_ready = set()


def db_path():
    return os.environ.get("DB_PATH", "records.db")


def connect():
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with closing(connect()) as con, con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS records(
          id INTEGER PRIMARY KEY, name TEXT, email TEXT, phone TEXT,
          fingerprint TEXT UNIQUE, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_email ON records(email);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_phone ON records(phone) WHERE phone != '';
        CREATE TABLE IF NOT EXISTS rejected(
          id INTEGER PRIMARY KEY, payload TEXT, status TEXT, reason TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP);""")


def normalize(rec):
    name = re.sub(r"\s+", " ", str(rec.get("name", "")).strip().lower())
    email = str(rec.get("email", "")).strip().lower()
    if "@" in email:
        local, domain = email.split("@", 1)
        email = local.split("+")[0] + "@" + domain  # drop +tags
    phone = re.sub(r"\D", "", str(rec.get("phone", "")))
    return {"name": name, "email": email, "phone": phone}


def validate(n):
    """Reason string if the record is a false positive (invalid/junk), else None."""
    if len(n["name"]) < 2 or n["name"] in JUNK:
        return "invalid or placeholder name"
    if not EMAIL_RE.match(n["email"]):
        return "malformed email"
    if n["phone"] and not 7 <= len(n["phone"]) <= 15:
        return "malformed phone"
    return None


def fingerprint(n):
    return hashlib.sha256(json.dumps(n, sort_keys=True).encode()).hexdigest()


def classify(con, rec):
    n = normalize(rec)
    reason = validate(n)
    if reason:
        return "false_positive", reason, n
    checks = (("fingerprint", fingerprint(n), "exact duplicate"),
              ("email", n["email"], "email already stored"),
              ("phone", n["phone"], "phone already stored"))
    for col, val, why in checks:  # col comes from this fixed tuple, never from input
        if val and con.execute(f"SELECT 1 FROM records WHERE {col}=?", (val,)).fetchone():
            return "redundant", why, n
    domain = n["email"].split("@")[1]
    for r in con.execute("SELECT name FROM records WHERE email LIKE ?", ("%@" + domain,)):
        if SequenceMatcher(None, n["name"], r["name"]).ratio() >= FUZZY:
            return "redundant", "near-duplicate of an existing record", n
    return "unique", None, n


def add_record(rec):
    with closing(connect()) as con, con:
        status, reason, n = classify(con, rec)
        if status == "unique":
            try:
                con.execute("INSERT INTO records(name,email,phone,fingerprint) VALUES(?,?,?,?)",
                            (n["name"], n["email"], n["phone"], fingerprint(n)))
            except sqlite3.IntegrityError:  # DB constraints are the final guard (race-safe)
                status, reason = "redundant", "blocked by database constraint"
        if status != "unique":
            con.execute("INSERT INTO rejected(payload,status,reason) VALUES(?,?,?)",
                        (json.dumps(rec, default=str), status, reason))
    return {"status": status, "reason": reason}


@app.before_request
def ensure_db():
    if db_path() not in _ready:
        init_db()
        _ready.add(db_path())


@app.post("/records")
def post_records():
    body = request.get_json(silent=True)
    items = body if isinstance(body, list) else [body]
    if not items or not all(isinstance(i, dict) for i in items):
        return jsonify(error="send a JSON object or a list of objects"), 400
    return jsonify(results=[add_record(i) for i in items])


@app.get("/records")
def list_records():
    with closing(connect()) as con:
        return jsonify([dict(r) for r in con.execute("SELECT id,name,email,phone,created_at FROM records")])


@app.get("/stats")
def stats():
    with closing(connect()) as con:
        stored = con.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        rej = {r["status"]: r["n"] for r in con.execute("SELECT status, COUNT(*) n FROM rejected GROUP BY status")}
    return jsonify(stored=stored, rejected=rej)


@app.get("/health")
def health():
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
