"""
Pulse - a live quiz / poll for a room full of phones.

    python pulse.py

Three pages:
    /quiz          students, on their phones
    /quiz/screen   the projector
    /quiz/admin    the instructor's control panel (password protected)

Everything the students do lives in Redis (or fakeredis). The questions live
in a SQLite file, pulse.db, so they survive restarts and you can edit them.
"""

import csv
import io
import json
import os
import socket
import sys
import time
import uuid
from typing import Any, List, Optional

# Look for auth.py / storage.py / pages.py next to this file, so Pulse works
# both as "python pulse.py" and when main.py imports it from the folder above.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import qrcode
import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

import auth
import storage
from auth import require_admin
from storage import (K_OPEN, K_STUDENTS, db, k_answer, k_answers, k_email,
                     k_reveal, k_student)

PORT = int(os.environ.get("PORT", "8000"))   # same variable main.py uses


def find_lan_ip():
    """Ask the OS which address it would use to reach the internet. No packet
    is actually sent - this is just how you learn your own Wi-Fi address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


LAN_IP = find_lan_ip()
storage.init_db()

router = APIRouter()

# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

_open_cache = {"qid": None, "question": None}     # so /quiz/state does not hit SQLite


def current_question():
    """The question that is open right now, or None. Cached in memory because
    150 phones ask for it every 2 seconds."""
    raw = db.get(K_OPEN)
    if not raw:
        return None
    qid = int(raw)
    if _open_cache["qid"] != qid:
        _open_cache["qid"], _open_cache["question"] = qid, storage.get_question(qid)
    return _open_cache["question"]


def forget_cache():
    _open_cache["qid"] = _open_cache["question"] = None


def join_url(request: Request) -> str:
    """The address students type or scan. Prefer the real LAN IP; fall back to
    whatever host the browser used to reach us."""
    if LAN_IP:
        return f"http://{LAN_IP}:{PORT}/quiz"
    return f"http://{request.headers.get('host', 'localhost')}/quiz"


def student_names(sids):
    """One round trip for many names."""
    pipe = db.pipeline()
    for sid in sids:
        pipe.hget(k_student(sid), "name")
    return pipe.execute()


def tally(question):
    """Turn the raw answers for one question into what the pages draw."""
    qid, qtype = question["id"], question["type"]
    sids = db.zrevrange(k_answers(qid), 0, -1)          # newest answer first
    values = db.mget([k_answer(qid, s) for s in sids]) if sids else []
    pairs = [(s, v) for s, v in zip(sids, values) if v is not None]

    if qtype == "choice":
        counts = [0] * len(question["options"])
        for _, v in pairs:
            i = int(v)
            if 0 <= i < len(counts):
                counts[i] += 1
        return {"counts": counts}

    if qtype == "scale":
        counts = [0] * 5
        for _, v in pairs:
            i = int(v)
            if 1 <= i <= 5:
                counts[i - 1] += 1
        total = sum(counts)
        avg = sum((i + 1) * c for i, c in enumerate(counts)) / total if total else 0
        return {"counts": counts, "average": round(avg, 2)}

    shown = pairs[:60]                                   # the wall shows the newest 60
    names = student_names([s for s, _ in shown])
    return {"answers": [{"name": n or "Someone", "answer": v} for (s, v), n in zip(shown, names)]}


def clear_answers(qid):
    """Throw away every answer to one question."""
    sids = db.zrange(k_answers(qid), 0, -1)
    if sids:
        db.delete(*[k_answer(qid, s) for s in sids])
    db.delete(k_answers(qid), k_reveal(qid))


def qr_svg(url, px=560):
    """The join QR, drawn as plain SVG so no image library or CDN is needed."""
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    n = len(matrix)
    dots = "".join(f'<rect x="{x}" y="{y}" width="1" height="1"/>'
                   for y, row in enumerate(matrix) for x, on in enumerate(row) if on)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" '
            f'viewBox="0 0 {n} {n}" shape-rendering="crispEdges">'
            f'<rect width="{n}" height="{n}" fill="#FFFFFF"/><g fill="#000000">{dots}</g></svg>')


# --------------------------------------------------------------------------
# Student endpoints (public)
# --------------------------------------------------------------------------

class JoinBody(BaseModel):
    name: str
    semester: str = "Other"
    email: Optional[str] = ""


class AnswerBody(BaseModel):
    student_id: str
    question_id: Any
    answer: Any


@router.post("/join")
def join(body: JoinBody):
    name = (body.name or "").strip()[:60]
    if not name:
        raise HTTPException(400, "Please type your name")
    email = (body.email or "").strip().lower()[:120]
    if email:                                   # same email twice = same student
        existing = db.get(k_email(email))
        if existing and db.exists(k_student(existing)):
            return {"student_id": existing, "name": db.hget(k_student(existing), "name")}
    sid = uuid.uuid4().hex[:12]
    db.hset(k_student(sid), mapping={"name": name, "semester": body.semester or "Other",
                                     "email": email, "joined_at": storage.now_iso()})
    db.lpush(K_STUDENTS, sid)
    if email:
        db.set(k_email(email), sid)
    return {"student_id": sid, "name": name}


@router.get("/state")
def state():
    """What every phone and the projector poll. Students are told about the
    open question and nothing else."""
    question = current_question()
    joined = db.llen(K_STUDENTS)
    if not question:
        return {"open_question": None, "joined": joined, "answered": 0,
                "results": None, "compare": None}

    reveal = bool(db.exists(k_reveal(question["id"])))
    shown = {"id": question["id"], "type": question["type"], "prompt": question["prompt"],
             "options": question["options"], "pie": question["pie"], "reveal": reveal}
    if reveal and question["correct_index"] is not None:
        shown["correct_index"] = question["correct_index"]

    compare = None
    if question["compare_with"]:
        other = storage.get_question(question["compare_with"])
        if other:
            compare = dict(tally(other), prompt=other["prompt"])
    return {"open_question": shown, "joined": joined,
            "answered": db.zcard(k_answers(question["id"])),
            "results": tally(question), "compare": compare}


@router.post("/answer")
def answer(body: AnswerBody):
    question = current_question()
    if not question or str(question["id"]) != str(body.question_id):
        raise HTTPException(400, "That question is not open right now")
    sid = str(body.student_id or "")
    if not db.exists(k_student(sid)):
        raise HTTPException(404, "Unknown student - please join again")

    if question["type"] == "choice":
        try:
            value = int(body.answer)
        except (TypeError, ValueError):
            raise HTTPException(400, "Answer must be an option number")
        if not 0 <= value < len(question["options"]):
            raise HTTPException(400, "That option does not exist")
    elif question["type"] == "scale":
        try:
            value = int(body.answer)
        except (TypeError, ValueError):
            raise HTTPException(400, "Answer must be a number from 1 to 5")
        if not 1 <= value <= 5:
            raise HTTPException(400, "Answer must be from 1 to 5")
    else:
        value = str(body.answer or "").strip()[:200]
        if not value:
            raise HTTPException(400, "Please type something")

    db.set(k_answer(question["id"], sid), value)          # one answer per student,
    db.zadd(k_answers(question["id"]), {sid: time.time()})  # changing it just overwrites
    return {"ok": True}


@router.get("/qr.svg")
def qr(request: Request):
    return Response(qr_svg(join_url(request)), media_type="image/svg+xml")


# --------------------------------------------------------------------------
# Login / logout
# --------------------------------------------------------------------------

class LoginBody(BaseModel):
    password: str = ""


@router.post("/admin/login")
def login(body: LoginBody, request: Request):
    ip = request.client.host if request.client else "unknown"
    if auth.locked_out(ip):
        raise HTTPException(429, "Too many attempts. Wait a minute and try again.")
    if not auth.password_ok(body.password):
        auth.record_failure(ip)
        raise HTTPException(401, "Wrong password")
    auth.clear_failures(ip)
    token, _ = auth.make_token()
    reply = JSONResponse({"token": token})
    reply.set_cookie(auth.COOKIE_NAME, token, httponly=True, samesite="lax",
                     max_age=auth.JWT_HOURS * 3600, path="/")
    return reply


@router.post("/admin/logout")
def logout(request: Request):
    claims = auth.read_claims(request)
    if claims:
        auth.revoke(claims)
    reply = JSONResponse({"ok": True})
    reply.delete_cookie(auth.COOKIE_NAME, path="/")
    return reply


# --------------------------------------------------------------------------
# Admin endpoints (every one behind require_admin)
# --------------------------------------------------------------------------

ADMIN = [Depends(require_admin)]


class QuestionBody(BaseModel):
    type: str = "choice"
    prompt: str = ""
    options: List[str] = []
    correct_index: Optional[int] = None
    pie: bool = False
    compare_with: Optional[int] = None


class MoveBody(BaseModel):
    direction: str = "up"


def clean(body: QuestionBody):
    if body.type not in ("choice", "text", "scale"):
        raise HTTPException(400, "type must be choice, text or scale")
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(400, "The question needs a prompt")
    options = [o.strip() for o in body.options if o.strip()] if body.type == "choice" else []
    if body.type == "choice" and not 2 <= len(options) <= 5:
        raise HTTPException(400, "A choice question needs between 2 and 5 options")
    correct = body.correct_index
    if body.type != "choice" or correct is None or not 0 <= correct < len(options):
        correct = None
    return {"type": body.type, "prompt": prompt, "options": options, "correct_index": correct,
            "pie": bool(body.pie) and body.type == "choice",
            "compare_with": body.compare_with if body.type == "scale" else None}


@router.get("/admin/questions", dependencies=ADMIN)
def admin_questions():
    questions = storage.list_questions()
    open_raw = db.get(K_OPEN)
    open_id = int(open_raw) if open_raw else None
    for q in questions:
        q["answers"] = db.zcard(k_answers(q["id"]))
        q["reveal"] = bool(db.exists(k_reveal(q["id"])))
        q["open"] = (q["id"] == open_id)
    return {"questions": questions, "open": open_id}


@router.post("/admin/question", dependencies=ADMIN)
def create_question(body: QuestionBody):
    return {"id": storage.save_question(None, clean(body))}


@router.put("/admin/question/{qid}", dependencies=ADMIN)
def edit_question(qid: int, body: QuestionBody):
    before = storage.get_question(qid)
    if not before:
        raise HTTPException(404, "No such question")
    data = clean(body)
    cleared = 0
    if data["options"] != before["options"]:      # the old answers no longer mean anything
        cleared = db.zcard(k_answers(qid))
        clear_answers(qid)
    storage.save_question(qid, data)
    forget_cache()
    return {"id": qid, "cleared_answers": cleared}


@router.delete("/admin/question/{qid}", dependencies=ADMIN)
def delete_question(qid: int):
    if not storage.get_question(qid):
        raise HTTPException(404, "No such question")
    storage.sql("UPDATE questions SET active=0, updated_at=? WHERE id=?", (storage.now_iso(), qid))
    if db.get(K_OPEN) == str(qid):
        db.delete(K_OPEN)
    forget_cache()
    return {"ok": True}


@router.post("/admin/question/{qid}/move", dependencies=ADMIN)
def move_question(qid: int, body: MoveBody):
    questions = storage.list_questions()
    order = [q["id"] for q in questions]
    if qid not in order:
        raise HTTPException(404, "No such question")
    i = order.index(qid)
    j = i - 1 if body.direction == "up" else i + 1
    if 0 <= j < len(order):
        order[i], order[j] = order[j], order[i]
    for position, qid2 in enumerate(order, start=1):     # renumber so positions stay tidy
        storage.sql("UPDATE questions SET position=? WHERE id=?", (position, qid2))
    return {"order": order}


@router.post("/admin/launch/{qid}", dependencies=ADMIN)
def launch(qid: int, fresh: int = 0):
    if not storage.get_question(qid):
        raise HTTPException(404, "No such question")
    if fresh:
        clear_answers(qid)
    db.set(K_OPEN, qid)                 # only one question is ever open
    forget_cache()
    return {"ok": True, "open": qid}


@router.post("/admin/close", dependencies=ADMIN)
def close():
    db.delete(K_OPEN)
    forget_cache()
    return {"ok": True}


@router.post("/admin/reveal/{qid}", dependencies=ADMIN)
def reveal(qid: int):
    question = storage.get_question(qid)
    if not question:
        raise HTTPException(404, "No such question")
    if question["correct_index"] is None:
        raise HTTPException(400, "This question has no correct answer to reveal")
    if db.exists(k_reveal(qid)):
        db.delete(k_reveal(qid))
        return {"reveal": False}
    db.set(k_reveal(qid), "1")
    return {"reveal": True}


@router.post("/admin/reset", dependencies=ADMIN)
def reset(scope: str = "answers"):
    if scope not in ("answers", "all"):
        raise HTTPException(400, "scope must be answers or all")
    storage.clear_redis(everything=(scope == "all"))
    forget_cache()
    return {"ok": True, "scope": scope}


@router.get("/admin/roster", dependencies=ADMIN)
def roster():
    sids = db.lrange(K_STUDENTS, 0, -1)
    pipe = db.pipeline()
    for sid in sids:
        pipe.hgetall(k_student(sid))
    students = [s for s in pipe.execute() if s]
    by_semester = {"1st": 0, "3rd": 0, "Other": 0}
    for s in students:
        by_semester[s.get("semester") if s.get("semester") in by_semester else "Other"] += 1
    return {"joined": len(students), "by_semester": by_semester,
            "students": [{"name": s.get("name", ""), "semester": s.get("semester", ""),
                          "joined_at": s.get("joined_at", "")} for s in students]}


@router.get("/admin/questions/export", dependencies=ADMIN)
def export_questions():
    return {"questions": storage.list_questions()}


@router.post("/admin/questions/import", dependencies=ADMIN)
def import_questions(payload: Any):
    items = payload.get("questions") if isinstance(payload, dict) else payload
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "Send a list of questions")
    cleaned = [clean(QuestionBody(**item)) for item in items]        # validate before destroying
    storage.sql("UPDATE questions SET active=0 WHERE active=1")
    for data in cleaned:
        storage.save_question(None, data)
    db.delete(K_OPEN)
    forget_cache()
    return {"imported": len(cleaned)}


@router.get("/export", dependencies=ADMIN)
def export_csv():
    """One row per answer, for the instructor to keep."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["student_name", "semester", "email", "question_id", "prompt",
                     "answer", "answered_at"])
    rows = 0
    for question in storage.list_questions(active_only=False):
        entries = db.zrange(k_answers(question["id"]), 0, -1, withscores=True)
        for sid, when in entries:
            value = db.get(k_answer(question["id"], sid))
            if value is None:
                continue
            student = db.hgetall(k_student(sid)) or {}
            if question["type"] == "choice" and question["options"]:
                i = int(value)
                value = question["options"][i] if 0 <= i < len(question["options"]) else value
            writer.writerow([student.get("name", ""), student.get("semester", ""),
                             student.get("email", ""), question["id"], question["prompt"], value,
                             time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(when))])
            rows += 1
    return Response(out.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="pulse-answers.csv"',
        "X-Row-Count": str(rows)})


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------

@router.get("", response_class=HTMLResponse, include_in_schema=False)
def student_page():
    return PAGE_STUDENT


@router.get("/screen", response_class=HTMLResponse, include_in_schema=False)
def screen_page(request: Request):
    return PAGE_SCREEN.replace("__JOIN_URL__", join_url(request))


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page(request: Request):
    # No token yet? Show the login box instead of the control panel.
    return PAGE_ADMIN if auth.read_claims(request) else PAGE_LOGIN


from pages import PAGE_ADMIN, PAGE_LOGIN, PAGE_SCREEN, PAGE_STUDENT  # noqa: E402

# --------------------------------------------------------------------------
# The app
# --------------------------------------------------------------------------

app = FastAPI(title="Pulse", description="Live quiz and polls for the AI Agents workshop.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)
app.include_router(router, prefix="/quiz")


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/quiz")     # so typing just the IP still works


if __name__ == "__main__":
    where = LAN_IP or "localhost"
    print(f"\n  Pulse"
          f"\n  storage    : {storage.STORAGE}"
          f"\n  lan ip     : {LAN_IP or 'not detected - using the browser host header'}"
          f"\n  jwt secret : {'from JWT_SECRET' if auth.SECRET_FROM_ENV else 'generated now (set JWT_SECRET to keep logins across restarts)'}"
          + ("" if auth.SECRET_FROM_ENV else f"\n               JWT_SECRET={auth.JWT_SECRET}")
          + f"\n\n  students   : http://{where}:{PORT}/quiz"
          f"\n  projector  : http://{where}:{PORT}/quiz/screen"
          f"\n  instructor : http://{where}:{PORT}/quiz/admin"
          f"\n  api docs   : http://{where}:{PORT}/docs\n", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
