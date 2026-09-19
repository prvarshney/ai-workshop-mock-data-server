# AI Agents Workshop — Chandigarh University

Two apps for a 3-hour workshop, both running on the instructor's laptop, both
working with no internet at all.

| | What it is |
| --- | --- |
| **Pulse** | A live quiz. Students join from their phones with a QR code; you launch questions and the results land on the projector. |
| **SkyBook** | A mock flight-booking API. Students point their own LLM agents at it, and every booking appears on a live dashboard. |

---

## Run everything

```bash
pip install -r requirements.txt
python main.py
```

One process, one port, one address to write on the board:

```
  index      : http://192.168.1.41:8000/
  students   : http://192.168.1.41:8000/quiz
  projector  : http://192.168.1.41:8000/quiz/screen
  instructor : http://192.168.1.41:8000/quiz/admin
  skybook    : http://192.168.1.41:8000/dashboard
  api docs   : http://192.168.1.41:8000/docs
```

| URL | What opens |
| --- | --- |
| `/` | Index page with big links to everything below |
| `/quiz` | **Pulse** — students, on their phones |
| `/quiz/screen` | **Pulse** — the projector: QR code, then live results |
| `/quiz/admin` | **Pulse** — your control panel (asks for the password) |
| `/dashboard` | **SkyBook** — live bookings from the students' agents |
| `/docs` | Swagger for both APIs together |
| `/health` | Is it up, and which storage it is using |

Change the port with `PORT=8080 python main.py`.

**Open the projector page only after joining the venue Wi-Fi.** The QR code is
built from the laptop's LAN IP, which changes with the network.

## Before the session

```bash
export ADMIN_PASSWORD="something-only-you-know"
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python main.py
```

The Pulse admin password defaults to `cu2026` — change it, because students can
reach the admin page too. Setting `JWT_SECRET` means restarting the server does
not log you out. On Windows PowerShell use `$env:ADMIN_PASSWORD="..."`.

## Redis is optional

Both apps keep their live state in Redis and **fall back to `fakeredis`
automatically** if it is not running, printing a warning. Everything still
works; the only difference is that data is lost when you stop the server.

| Platform | Command |
| --- | --- |
| macOS | `brew install redis` then `brew services start redis` |
| Docker | `docker run -d -p 6379:6379 --name workshop-redis redis` |
| Windows | [Memurai](https://www.memurai.com/), or Docker / WSL |

The two apps share one Redis database but never touch each other's keys —
Pulse owns everything under `pulse:`, SkyBook owns the rest. Neither reset
button affects the other app, and `smoke_test_all.py` checks exactly that.

## Finding your LAN IP

| Platform | Command |
| --- | --- |
| macOS | `ipconfig getifaddr en0` |
| Linux | `hostname -I` |
| Windows | `ipconfig` → "IPv4 Address" |

`main.py` prints it on startup too. If phones cannot reach you it is almost
always the laptop firewall — allow incoming connections on the port.

## Running one app on its own

Rarely needed, but both still work alone. They use the same `PORT` (default
8000), so run one at a time — or give one a different port:

```bash
python mock_server.py                # SkyBook only, on 8000
PORT=8001 python pulse/pulse.py      # Pulse only, on 8001
```

## Tests

```bash
python smoke_test_all.py      # 15 checks: the two apps sharing one process
python smoke_test.py          # 26 checks: SkyBook on its own
python pulse/smoke_test.py    # 40 checks: Pulse on its own
```

Each test starts what it needs and uses throwaway data, so none of them
disturb a live session — except `smoke_test.py`, which calls SkyBook's
`/reset`. Do not run that one mid-workshop.

## Files

| File | What it is |
| --- | --- |
| `main.py` | Runs both apps together on one port — **start here** |
| `mock_server.py` | SkyBook: the flight API and its dashboard |
| `pulse/` | Pulse: the quiz app (`pulse.py`, `pages.py`, `storage.py`, `auth.py`) |
| `pulse/pulse.db` | The question bank — your content, committed to the repo |
| `SKYBOOK.md` | SkyBook in detail: endpoints, data, curl examples |
| `pulse/README.md` | Pulse in detail: running a session, endpoints, settings |

## Detailed docs

- **[SkyBook](SKYBOOK.md)** — every endpoint, the flight and weather data, `/reset`
- **[Pulse](pulse/README.md)** — running a session, the question editor, exports
