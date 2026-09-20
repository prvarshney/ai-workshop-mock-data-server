# AI Agents Workshop — Chandigarh University

**One service, one port, one process** — started with a single command and
working with no internet at all. It does two jobs:

| | What it does |
| --- | --- |
| **Quiz** (`/quiz`) | Students join from their phones with a QR code; you launch questions and the results land on the projector. |
| **Flights** (`/dashboard`) | A mock flight-booking API. Students point their own LLM agents at it, and every booking appears on a live dashboard. |

They share one port, one `/docs`, one Redis connection and one startup command.
The code is split across files only to keep each one readable — `mock_server.py`
for flights, `pulse/` for the quiz — but at runtime it is a single service.

---

## Run everything

```bash
pip install -r requirements.txt
./start.sh                 # Windows: start.bat
```

The first run writes a `.env` next to the script with a freshly generated
`JWT_SECRET`. **Open it and change `ADMIN_PASSWORD`** — that is the only setting
you really must edit. `.env` is gitignored, so your password stays out of the
repo.

`start.sh` loads `.env`, checks the packages are installed, refuses to start if
the port is already busy, and then runs `main.py`. To skip it and run the server
directly:

```bash
python main.py
```

`python mock_server.py` and `python pulse/pulse.py` do the same thing — each
hands over to `main.py`, so whichever file you run, you get both apps. There is
no way to accidentally start half the workshop.

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
| `/docs` | Swagger for the flight API the agents call (the quiz endpoints are deliberately left out) |
| `/health` | Is it up, and which storage it is using |

Change the port with `PORT=8080 python main.py`.

**Open the projector page only after joining the venue Wi-Fi.** The QR code is
built from the laptop's LAN IP, which changes with the network.

## Before the session

Edit `.env`:

```ini
ADMIN_PASSWORD=something-only-you-know
JWT_SECRET=<generated for you on first run - keep it>
JWT_HOURS=12
PORT=8000
REDIS_URL=redis://localhost:6379/0
```

The Pulse admin password defaults to `cu2026` — change it, because students can
reach the admin page too. `start.sh` warns you while it is still the default.
Keeping `JWT_SECRET` fixed means restarting the server does not log you out.

Prefer environment variables? They still work, and they win over `.env`:

```bash
ADMIN_PASSWORD="..." PORT=9000 python main.py
```

## Running it on a server with Docker

If you start the server over SSH with `./start.sh`, closing the SSH session
kills it — the shell sends `SIGHUP` to everything it started. Docker fixes that
properly: the container keeps running when you log out, restarts if it crashes,
and comes back after a reboot.

On a fresh Ubuntu/Debian server:

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker "$USER"      # then log out and back in

git clone git@github.com:prvarshney/ai-workshop-mock-data-server.git
cd ai-workshop-mock-data-server
```

Create a `.env` (the same file `start.sh` uses — `docker compose` reads it
automatically):

```ini
ADMIN_PASSWORD=something-only-you-know
JWT_SECRET=paste-64-hex-chars-here
PORT=8000
```

Generate the secret with
`python3 -c 'import secrets; print(secrets.token_hex(32))'`. Compose refuses to
start without `JWT_SECRET`, on purpose — without a fixed one, every restart
logs you out.

```bash
docker compose up -d --build     # build and start, in the background
docker compose logs -f           # watch the request log (Ctrl+C just stops watching)
docker compose ps                # is it healthy?
docker compose restart           # after pulling new code
docker compose down              # stop; the data volumes stay
```

Then open `http://<server-ip>:8000/`. You can close the SSH session — it keeps
running.

| | |
| --- | --- |
| **Survives SSH exit / crash / reboot** | `restart: unless-stopped` on both containers |
| **Redis** | Runs as its own container; no install needed on the host |
| **Your questions** | `pulse.db` lives in a Docker volume, so edits survive rebuilds |
| **Port** | `PORT` in `.env` is the port on the server. `PORT=80` maps host 80 to the container |
| **Behind a domain or proxy** | Set `PUBLIC_HOST=quiz.example.com` so the join QR points at the right address |

`PUBLIC_HOST` matters because inside a container the app cannot see the
server's LAN address — it would otherwise put the container's private IP in the
QR code. Left unset, the QR uses whatever address the browser used to reach the
page, which is right for a plain `http://server-ip:8000` setup.

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

Rarely needed. Set `SOLO=1` to stop the hand-over to `main.py`:

```bash
SOLO=1 python mock_server.py             # SkyBook only  (no /quiz)
SOLO=1 python pulse/pulse.py             # Pulse only    (no /dashboard)
SOLO=1 PORT=8001 python pulse/pulse.py   # ...on another port
```

Without `SOLO`, both files start the full app on `PORT` (default 8000).

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
| `start.sh` / `start.bat` | Loads `.env` and starts the server — **start here** |
| `Dockerfile` / `docker-compose.yml` | Running it on a server, with Redis and restart-on-crash |
| `.env` | Your password, signing secret and port. Created on first run, gitignored |
| `main.py` | Runs both apps together on one port |
| `mock_server.py` | SkyBook: the flight API and its dashboard |
| `pulse/` | Pulse: the quiz app (`pulse.py`, `pages.py`, `storage.py`, `auth.py`) |
| `pulse/pulse.db` | The question bank — your content, committed to the repo |
| `SKYBOOK.md` | SkyBook in detail: endpoints, data, curl examples |
| `pulse/README.md` | Pulse in detail: running a session, endpoints, settings |

## Detailed docs

- **[SkyBook](SKYBOOK.md)** — every endpoint, the flight and weather data, `/reset`
- **[Pulse](pulse/README.md)** — running a session, the question editor, exports
