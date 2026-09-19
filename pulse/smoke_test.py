"""
End-to-end check for Pulse.

    python smoke_test.py

It starts its own copy of the server on port 8123 with a throwaway database,
so it never touches your real pulse.db or a live session. It restarts the
server half way through to prove the question edits really are on disk.
"""

import json
import os
import pathlib
import signal
import subprocess
import sys
import time

import jwt
import requests

HERE = pathlib.Path(__file__).parent
PORT = 8123
BASE = f"http://localhost:{PORT}"
TEST_DB = "/tmp/pulse_smoke.db"
SECRET = "smoke-test-secret-value-32-bytes-long"
PASSWORD = "cu2026"

# SOLO=1 so we test Pulse by itself; without it pulse.py hands over to main.py
ENV = dict(os.environ, SOLO="1", PORT=str(PORT), PULSE_DB=TEST_DB, JWT_SECRET=SECRET,
           ADMIN_PASSWORD=PASSWORD, REDIS_URL=os.environ.get("SMOKE_REDIS_URL",
                                                             "redis://localhost:6379/15"))
passed = failed = 0
server = None


def check(label, ok, extra=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}   {extra}")


def start():
    global server
    server = subprocess.Popen([sys.executable, str(HERE / "pulse.py")], env=ENV,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(80):
        try:
            if requests.get(BASE + "/quiz/state", timeout=1).ok:
                return
        except Exception:
            time.sleep(0.25)
    raise SystemExit("server did not start:\n" + (server.stdout.read() if server.stdout else ""))


def stop():
    if server:
        server.send_signal(signal.SIGINT)
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def bearer(token):
    return {"Authorization": "Bearer " + token}


def get(path, **kw):   return requests.get(BASE + path, timeout=10, **kw)
def post(path, **kw):  return requests.post(BASE + path, timeout=10, **kw)


def questions(token):
    return get("/quiz/admin/questions", headers=bearer(token)).json()["questions"]


def sqlite_rows():
    import sqlite3
    con = sqlite3.connect(TEST_DB)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("SELECT * FROM questions ORDER BY position, id")]
    con.close()
    return rows


# ==========================================================================
pathlib.Path(TEST_DB).unlink(missing_ok=True)
print("\nPulse smoke test")
start()
print("  storage:", "fakeredis" if "fakeredis" in (ENV.get("REDIS_URL") or "") else ENV["REDIS_URL"])

# ---- authentication ------------------------------------------------------
print("\n-- authentication")
r = post("/quiz/admin/login", json={"password": PASSWORD})
check("correct password returns a token", r.status_code == 200 and "token" in r.json(), r.text)
TOKEN = r.json()["token"]
check("login also sets an HttpOnly cookie", "pulse_admin" in r.cookies)

second = post("/quiz/admin/login", json={"password": PASSWORD}).json()["token"]

check("admin endpoint without a token -> 401", get("/quiz/admin/questions").status_code == 401)
check("admin endpoint with a token -> 200",
      get("/quiz/admin/questions", headers=bearer(TOKEN)).status_code == 200)

post("/quiz/admin/logout", headers=bearer(second))
check("a token reused after logout -> 401",
      get("/quiz/admin/questions", headers=bearer(second)).status_code == 401)

forged = jwt.encode({"sub": "admin", "jti": "x", "iat": int(time.time()),
                     "exp": int(time.time()) + 600}, "a-different-secret", algorithm="HS256")
check("a token signed with another secret -> 401",
      get("/quiz/admin/questions", headers=bearer(forged)).status_code == 401)

codes = [post("/quiz/admin/login", json={"password": "wrong"}).status_code for _ in range(6)]
check("wrong password -> 401", codes[0] == 401, str(codes))
check("six wrong attempts -> 429", codes[:5] == [401] * 5 and codes[5] == 429, str(codes))

# ---- the session ---------------------------------------------------------
print("\n-- running a session")
state = get("/quiz/state").json()
check("nothing is open before the first launch", state["open_question"] is None)

students = []
for name, sem, email in [("Aarav", "1st", "aarav@example.com"), ("Diya", "3rd", "diya@example.com"),
                         ("Vihaan", "Other", "")]:
    students.append(post("/quiz/join", json={"name": name, "semester": sem, "email": email}).json())
check("three students joined", get("/quiz/state").json()["joined"] == 3)
again = post("/quiz/join", json={"name": "Aarav again", "semester": "1st",
                                 "email": "aarav@example.com"}).json()
check("the same email gives back the same student_id",
      again["student_id"] == students[0]["student_id"])

QS = questions(TOKEN)
q1, q2, q3, q4 = QS[0]["id"], QS[1]["id"], QS[2]["id"], QS[3]["id"]

post(f"/quiz/admin/launch/{q1}", headers=bearer(TOKEN))
check("launching q1 opens it", get("/quiz/state").json()["open_question"]["id"] == q1)
for student, choice in zip(students, [0, 0, 1]):
    post("/quiz/answer", json={"student_id": student["student_id"], "question_id": q1,
                               "answer": choice})
state = get("/quiz/state").json()
counts = state["results"]["counts"]
check("choice counts are 2 / 1 / 0, and nothing else was picked",
      counts[:3] == [2, 1, 0] and sum(counts) == 3, str(counts))
check("answered = 3", state["answered"] == 3)

r = post("/quiz/answer", json={"student_id": students[0]["student_id"], "question_id": q2,
                               "answer": 3})
check("answering a question that is not open -> 400", r.status_code == 400, r.text)

post(f"/quiz/admin/launch/{q3}", headers=bearer(TOKEN))
post("/quiz/answer", json={"student_id": students[0]["student_id"], "question_id": q3,
                           "answer": "AI is pattern matching"})
post("/quiz/answer", json={"student_id": students[1]["student_id"], "question_id": q3,
                           "answer": "Machines that learn"})
answers = get("/quiz/state").json()["results"]["answers"]
check("a text answer shows up on the wall",
      any(a["answer"] == "AI is pattern matching" for a in answers), str(answers))
post("/quiz/answer", json={"student_id": students[0]["student_id"], "question_id": q3,
                           "answer": "Changed my mind"})
answers = get("/quiz/state").json()["results"]["answers"]
check("re-answering replaces, it does not duplicate",
      len(answers) == 2 and any(a["answer"] == "Changed my mind" for a in answers) and
      not any(a["answer"] == "AI is pattern matching" for a in answers), str(answers))

post(f"/quiz/admin/launch/{q4}", headers=bearer(TOKEN))
check("correct_index is hidden before reveal", "correct_index" not in get("/quiz/state").json()["open_question"])
post(f"/quiz/admin/reveal/{q4}", headers=bearer(TOKEN))
check("correct_index appears once reveal is on",
      get("/quiz/state").json()["open_question"].get("correct_index") == 1)
post(f"/quiz/admin/reveal/{q4}", headers=bearer(TOKEN))
check("correct_index hidden again after toggling reveal off",
      "correct_index" not in get("/quiz/state").json()["open_question"])

# ---- export and resets ---------------------------------------------------
print("\n-- export and resets")
csv_text = get("/quiz/export", headers=bearer(TOKEN)).text
rows = [ln for ln in csv_text.strip().splitlines() if ln][1:]
check("CSV has one row per answer (5)", len(rows) == 5, f"{len(rows)} rows")
check("CSV writes the option text, not the number",
      any(",1st," in ln or ",3rd," in ln for ln in rows), rows[0] if rows else "")

post("/quiz/admin/reset?scope=answers", headers=bearer(TOKEN))
state = get("/quiz/state").json()
check("reset answers keeps the students", state["joined"] == 3)
check("reset answers closes the open question", state["open_question"] is None)

post("/quiz/admin/reset?scope=all", headers=bearer(TOKEN))
check("reset all empties the roster", get("/quiz/state").json()["joined"] == 0)
check("reset all leaves SQLite alone", len(sqlite_rows()) == 9)

# ---- editing the bank ----------------------------------------------------
print("\n-- editing the question bank")
edited = "EDITED: in one line, what is AI?"
body = {"type": "text", "prompt": edited, "options": [], "correct_index": None,
        "pie": False, "compare_with": None}
r = requests.put(BASE + f"/quiz/admin/question/{q3}", json=body, headers=bearer(TOKEN))
check("PUT edits a question", r.status_code == 200, r.text)

victim = QS[6]["id"]
requests.delete(BASE + f"/quiz/admin/question/{victim}", headers=bearer(TOKEN))
check("a deleted question is gone from the admin list",
      victim not in [q["id"] for q in questions(TOKEN)])
check("a deleted question is still in SQLite with active=0",
      any(r["id"] == victim and r["active"] == 0 for r in sqlite_rows()))

before = [q["id"] for q in questions(TOKEN)]
q8 = QS[7]["id"]
post(f"/quiz/admin/question/{q8}/move", json={"direction": "up"}, headers=bearer(TOKEN))
after = [q["id"] for q in questions(TOKEN)]
i = before.index(q8)
check("moving a question up swaps it with the one above",
      after[i - 1] == q8 and after[i] == before[i - 1], f"{before} -> {after}")

# ---- restart -------------------------------------------------------------
print("\n-- restart the server")
stop()
start()
check("the edited prompt survived the restart",
      any(q["prompt"] == edited for q in questions(TOKEN)))
check("the deleted question is still deleted after the restart",
      victim not in [q["id"] for q in questions(TOKEN)])
check("the new order survived the restart", [q["id"] for q in questions(TOKEN)] == after)
check("the same token still works after a restart (JWT_SECRET is fixed)",
      get("/quiz/admin/questions", headers=bearer(TOKEN)).status_code == 200)

# ---- pages ---------------------------------------------------------------
print("\n-- pages")
check("student page renders", "PULSE" in get("/quiz").text)
check("screen page renders", "Scan to join" in get("/quiz/screen").text)
check("admin page shows the login box when logged out",
      "Instructor login" in get("/quiz/admin").text)
check("admin page shows the panel when the cookie is set",
      "Add question" in requests.get(BASE + "/quiz/admin",
                                     cookies={"pulse_admin": TOKEN}, timeout=10).text)
svg = get("/quiz/qr.svg")
check("QR renders as SVG", svg.headers["content-type"].startswith("image/svg") and
      svg.text.startswith("<svg"))
check("/docs is available", get("/docs").status_code == 200)

stop()
print(f"\n  {passed} passed, {failed} failed\n")
sys.exit(1 if failed else 0)
