"""
Where Pulse keeps things.

Two stores, on purpose:
  Redis   - the LIVE session: who joined, what they answered, which question
            is open. Fast, and easy to wipe between sessions. If Redis is not
            running we fall back to fakeredis so the app still starts.
  SQLite  - the QUESTION BANK (pulse.db). A real file that survives restarts,
            that the instructor can edit, and that you can commit to git.

A "reset" only ever clears Redis. Your questions are never touched by it.
"""

import json
import os
import sqlite3
import time
from pathlib import Path

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DB_PATH = Path(os.environ.get("PULSE_DB") or Path(__file__).with_name("pulse.db"))

# --------------------------------------------------------------------------
# Redis (or fakeredis)
# --------------------------------------------------------------------------


def _connect_redis():
    """Return (client, name). Falls back to fakeredis when Redis is missing."""
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        return client, "redis"
    except Exception as exc:
        import fakeredis
        print(f"WARNING: cannot reach Redis at {REDIS_URL} ({exc.__class__.__name__}); "
              "using in-memory fakeredis - joins and answers are lost when Pulse stops.",
              flush=True)
        return fakeredis.FakeRedis(decode_responses=True), "fakeredis"


db, STORAGE = _connect_redis()

# Every Redis key Pulse uses starts with "pulse:" so it can share a database
# with other apps, and so a reset never deletes anything that is not ours.
K_OPEN = "pulse:open"
K_STUDENTS = "pulse:students"


def k_student(sid):      return f"pulse:student:{sid}"
def k_email(email):      return f"pulse:email:{email.strip().lower()}"
def k_answer(qid, sid):  return f"pulse:answer:{qid}:{sid}"
def k_answers(qid):      return f"pulse:answers:{qid}"       # sorted set: member=sid, score=time
def k_reveal(qid):       return f"pulse:reveal:{qid}"


def clear_redis(everything: bool) -> None:
    """Delete our keys. everything=False keeps the students who already joined."""
    patterns = ["pulse:answer:*", "pulse:answers:*", "pulse:reveal:*", K_OPEN]
    if everything:
        patterns += ["pulse:student:*", "pulse:email:*", K_STUDENTS, "pulse:login_attempts:*"]
    for pattern in patterns:
        keys = list(db.scan_iter(match=pattern, count=500)) if "*" in pattern else [pattern]
        if keys:
            db.delete(*keys)


# --------------------------------------------------------------------------
# SQLite question bank
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id            INTEGER PRIMARY KEY,
    position      INTEGER,
    type          TEXT CHECK(type IN ('choice','text','scale')),
    prompt        TEXT,
    options       TEXT,             -- JSON array; empty for text/scale
    correct_index INTEGER,          -- NULL when there is no right answer
    pie           INTEGER DEFAULT 0,-- 1 = draw a donut on the projector
    compare_with  INTEGER,          -- id of an earlier question to show beside this one
    active        INTEGER DEFAULT 1,
    updated_at    TEXT)
"""

# Inserted once, the very first time pulse.db is created.
# compare_with here means "the question at this position".
SEED = [
    ("choice", "Which semester are you in?",
     ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"], None, 1, None),
    ("scale", "How confident are you explaining what an AI agent is?", [], None, 0, None),
    ("text", "In one line: what is AI?", [], None, 0, None),
    ("choice", "How does an AI model actually work?",
     ["It searches the internet", "It predicts the next word",
      "It has rules written by programmers", "I have no idea"], 1, 0, None),
    ("choice", "A bat and a ball cost ₹110. The bat costs ₹100 more than the ball. "
               "What does the ball cost?", ["₹10", "₹5", "₹100", "₹55"], 1, 0, None),
    ("text", "Now that you have a mini brain on your laptop — what would you make it do for you?",
     [], None, 0, None),
    ("choice", "Which body part is the LLM?", ["Brain", "Hands", "Eyes", "Heart"], 0, 0, None),
    ("choice", "Which HTTP method CREATES something?", ["GET", "POST", "PUT", "DELETE"], 1, 0, None),
    ("scale", "How confident are you now explaining what an AI agent is?", [], None, 0, 2),
]


def sql(query, args=(), fetch=None):
    """Run one statement. fetch='one'|'all', or None to get the new row id."""
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(query, args)
        out = cur.fetchone() if fetch == "one" else cur.fetchall() if fetch == "all" else cur.lastrowid
        con.commit()
        return out
    finally:
        con.close()


def now_iso():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    """Create pulse.db on first run and put the starting questions in it."""
    sql("PRAGMA journal_mode=WAL")       # lets the projector read while the admin writes
    sql(SCHEMA)
    if sql("SELECT COUNT(*) AS n FROM questions", fetch="one")["n"]:
        return                           # already has questions - leave them alone
    ids = []
    for position, (qtype, prompt, options, correct, pie, _) in enumerate(SEED, start=1):
        ids.append(sql(
            "INSERT INTO questions (position, type, prompt, options, correct_index, pie,"
            " compare_with, active, updated_at) VALUES (?,?,?,?,?,?,NULL,1,?)",
            (position, qtype, prompt, json.dumps(options), correct, pie, now_iso())))
    for position, seed in enumerate(SEED, start=1):        # link the "compare with" pairs
        if seed[5]:
            sql("UPDATE questions SET compare_with=? WHERE id=?", (ids[seed[5] - 1], ids[position - 1]))


def to_dict(row):
    """One SQLite row -> a plain dict the pages can use."""
    if row is None:
        return None
    return {
        "id": row["id"], "position": row["position"], "type": row["type"],
        "prompt": row["prompt"], "options": json.loads(row["options"] or "[]"),
        "correct_index": row["correct_index"], "pie": bool(row["pie"]),
        "compare_with": row["compare_with"], "active": row["active"],
        "updated_at": row["updated_at"],
    }


def list_questions(active_only=True):
    where = "WHERE active=1" if active_only else ""
    rows = sql(f"SELECT * FROM questions {where} ORDER BY position, id", fetch="all")
    return [to_dict(r) for r in rows]


def get_question(qid, active_only=True):
    where = " AND active=1" if active_only else ""
    return to_dict(sql(f"SELECT * FROM questions WHERE id=?{where}", (qid,), fetch="one"))


def next_position():
    row = sql("SELECT MAX(position) AS p FROM questions", fetch="one")
    return (row["p"] or 0) + 1


def save_question(qid, data):
    """Create (qid=None) or update one question. Returns its id."""
    fields = (data["type"], data["prompt"], json.dumps(data["options"]),
              data["correct_index"], 1 if data["pie"] else 0, data["compare_with"], now_iso())
    if qid:
        sql("UPDATE questions SET type=?, prompt=?, options=?, correct_index=?, pie=?,"
            " compare_with=?, updated_at=? WHERE id=?", fields + (qid,))
        return qid
    return sql("INSERT INTO questions (position, type, prompt, options, correct_index, pie,"
               " compare_with, active, updated_at) VALUES (?,?,?,?,?,?,?,1,?)",
               (next_position(),) + fields)
