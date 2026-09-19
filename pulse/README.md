# ● Pulse — live quiz and polls for the AI Agents workshop

Students join from their phones by scanning a QR code. You launch a question
from your laptop; it pops onto every phone within two seconds and the answers
appear live on the projector.

No internet needed. No accounts. Nothing for students to install.

---

## 1. Install

```bash
pip install -r requirements.txt
```

Python 3.10 or newer (3.9 also works).

## 2. Run

```bash
python pulse.py
```

`python pulse.py` actually starts **both** Pulse and SkyBook, by handing over
to `main.py` in the folder above — use `SOLO=1 python pulse.py` for Pulse alone (see the [project README](../README.md)). Everything below
applies either way; only the port changes.

You will see something like:

```
  Pulse
  storage    : redis
  lan ip     : 192.168.1.41
  jwt secret : generated now (set JWT_SECRET to keep logins across restarts)
               JWT_SECRET=7f3c...

  students   : http://192.168.1.41:8000/quiz
  projector  : http://192.168.1.41:8000/quiz/screen
  instructor : http://192.168.1.41:8000/quiz/admin
  api docs   : http://192.168.1.41:8000/docs
```

| Page | Who opens it |
| --- | --- |
| `/quiz` | students, on their phones |
| `/quiz/screen` | the projector — shows the QR code until you launch something |
| `/quiz/admin` | you, on the laptop (asks for the password) |
| `/docs` | Swagger. Running the whole workshop app leaves the quiz endpoints out of it on purpose; `SOLO=1 python pulse.py` shows them |

**Open `/quiz/screen` only after you are on the venue Wi-Fi.** The QR code is
built from the laptop's LAN IP, and that address changes with the network.

## 3. Before the session — set two things

```bash
export ADMIN_PASSWORD="something-only-you-know"
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python pulse.py
```

- **`ADMIN_PASSWORD`** defaults to `cu2026`. Change it — the students can reach
  the admin page too, they just cannot get in without the password.
- **`JWT_SECRET`** is what signs your login. If you do not set it, a new one is
  made at every start, so restarting the server logs you out. Set it once and
  one login lasts the whole session.

A login is good for 12 hours, so you log in once and forget about it.

On Windows PowerShell, use `$env:ADMIN_PASSWORD="..."` instead of `export`.

### All the settings

| Variable | Default | What it does |
| --- | --- | --- |
| `PORT` | `8000` | Port to listen on |
| `REDIS_URL` | `redis://localhost:6379/0` | Where the live state goes |
| `ADMIN_PASSWORD` | `cu2026` | The instructor password |
| `JWT_SECRET` | random each start | Signs the login token |
| `JWT_HOURS` | `12` | How long a login lasts |
| `PULSE_DB` | `pulse.db` beside the code | The question bank file |

## 4. Redis is optional

Pulse keeps the live session in Redis. **If Redis is not running it falls back
to `fakeredis` automatically** and prints a warning. Everything works the same;
the only difference is that joins and answers are lost if you restart the
server. Your questions are in SQLite either way and are never affected.

| Platform | Command |
| --- | --- |
| macOS | `brew install redis` then `brew services start redis` |
| Docker (any OS) | `docker run -d -p 6379:6379 --name pulse-redis redis` |
| Windows | Install [Memurai](https://www.memurai.com/), or use Docker / WSL |

## 5. Telling students where to go

Everyone must be on the same Wi-Fi. The QR code on the projector is the easy
path; the URL is printed under it for anyone whose camera will not cooperate.

| Platform | How to find your LAN IP |
| --- | --- |
| macOS | `ipconfig getifaddr en0` |
| Linux | `hostname -I` |
| Windows | `ipconfig` → look for "IPv4 Address" |

If phones cannot reach you it is almost always the laptop firewall — allow
incoming connections on port 8000.

## 6. Running a session

1. Open `/quiz/screen` on the projector. Students scan and join; the counter in
   the corner climbs.
2. On `/quiz/admin`, hit **Launch** next to a question. It appears on every
   phone within 2 seconds and the results start filling in.
3. **Reveal** (on questions that have a right answer) turns the correct bar
   green on the projector. Great for the bat-and-ball one.
4. **Close** puts the phones back to the waiting screen.
5. **Launch fresh** re-runs a question after clearing its old answers.

Students get a **Leave** button in the corner of their page. It asks them to
confirm, then signs that phone out and returns it to the join form. **Their
answers are kept** — they stay on your roster, in the tallies and in the CSV.
Useful when a handset is being passed around, or someone typed the wrong name
and wants to join again.

The question editor takes prompt, type, options (one per line), the correct
answer, whether to draw a donut, a **timer**, and which earlier scale question
to compare against. Everything saves straight to `pulse.db`.

### Timers

Set **Timer (seconds after launch)** on a question and the countdown starts the
moment you hit Launch. It shows big on the projector next to the prompt, and on
every phone as "1m 30s left to answer". Anything over a minute is written as
minutes and seconds, and both sit in a fixed-width slot so the prompt and the
wording never shift as the digits change.

When it reaches zero the phones stop accepting answers — buttons grey out and a
late submission is refused — but **the question stays on the projector** with
all its results and the answered / still-to-answer lists, so you can talk
through it. Closing is still your call, with the Close button.

Leave it at `0` for no time limit. **Launch** or **Launch fresh** restarts the
clock, so you can re-run a question and give the room another go.

Question 9 is set to compare with question 2 — the same confidence question
asked at the start and at the end. The projector shows both, side by side,
with both averages. That is the closing slide.

## 7. Between sessions

- **Reset answers** — clears every answer, keeps the students who joined and
  keeps their phones signed in.
- **Reset everything** — clears the students too, and signs every phone out:
  within a couple of seconds each student is back at the join form and has to
  enter their name again. Use it between two different groups.
- **Export answers (CSV)** — one row per answer, with names and timestamps.
- Neither reset ever touches your questions.

## 8. Endpoints

Students (no login):

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/quiz` | The student page |
| POST | `/quiz/join` | `{name, semester, email?}` → `{student_id, name}` |
| GET | `/quiz/state` | The open question plus live results |
| POST | `/quiz/answer` | `{student_id, question_id, answer}` |
| GET | `/quiz/board` | Everything the projector shows, including who answered what |
| GET | `/quiz/qr.svg` | The join QR code |
| GET | `/quiz/screen` | The projector page |

Login:

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/quiz/admin` | Login box, or the control panel once you are in |
| POST | `/quiz/admin/login` | `{password}` → token + cookie. 5 wrong tries a minute → 429 |
| POST | `/quiz/admin/logout` | Kills the token |

Instructor only (401 without a login):

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/quiz/admin/questions` | The bank, with live answer counts |
| POST | `/quiz/admin/question` | Create |
| PUT | `/quiz/admin/question/{id}` | Edit |
| DELETE | `/quiz/admin/question/{id}` | Soft delete (`active=0`) |
| POST | `/quiz/admin/question/{id}/move` | `{direction: "up"\|"down"}` |
| POST | `/quiz/admin/launch/{id}?fresh=0\|1` | Open a question |
| POST | `/quiz/admin/close` | Close the open question |
| POST | `/quiz/admin/reveal/{id}` | Toggle the correct answer |
| POST | `/quiz/admin/reset?scope=answers\|all` | Clear Redis |
| GET | `/quiz/admin/roster` | Who has joined |
| GET | `/quiz/admin/questions/export` | The bank as JSON |
| POST | `/quiz/admin/questions/import` | Replace the bank from JSON |
| GET | `/quiz/export` | All answers as CSV |

With `curl`, send the token as a header:

```bash
TOKEN=$(curl -s -X POST localhost:8000/quiz/admin/login \
  -H 'Content-Type: application/json' -d '{"password":"cu2026"}' | python -c 'import json,sys;print(json.load(sys.stdin)["token"])')

curl -H "Authorization: Bearer $TOKEN" localhost:8000/quiz/admin/questions
```

## 9. Mounting it inside another app

`pulse.py` exposes a plain `router`, so Pulse can live inside a bigger FastAPI
app at the same `/quiz` URLs:

```python
from fastapi import FastAPI
from pulse import router          # importing pulse.py also creates pulse.db

app = FastAPI()
app.include_router(router, prefix="/quiz")
```

Keep the `/quiz` prefix — the pages fetch absolute paths like `/quiz/state`.

## 10. Checking it works

```bash
python smoke_test.py
```

40 checks: login, rate limiting, logout, forged tokens, joining, answering,
reveal, CSV export, both resets, editing the bank, and a server restart to
prove the edits are really on disk. It starts its own server on port 8123 with
a throwaway database, so it never touches your real `pulse.db` or a live
session.

## Files

| File | What it is |
| --- | --- |
| `pulse.py` | The app: API, routes, startup |
| `pages.py` | The four pages (student, projector, login, control panel) |
| `storage.py` | Redis/fakeredis connection and the SQLite helpers |
| `auth.py` | Password check, JWT issue/verify, `require_admin` |
| `pulse.db` | The question bank. Commit it — it is your content |
| `smoke_test.py` | End-to-end check |
