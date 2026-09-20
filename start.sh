#!/usr/bin/env bash
#
# Start the whole workshop app.
#
#     ./start.sh
#
# Settings live in a .env file next to this script. The first run creates one
# with a freshly generated signing secret; open it and change the password.
# .env is gitignored, so your password never lands in the repo.

set -euo pipefail
cd "$(dirname "$0")"

# ---------------------------------------------------------------- python ---
if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"                 # the virtualenv, if there is one
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
else
    echo "Python 3 is not installed. Install it and try again." >&2
    exit 1
fi

# ------------------------------------------------------------------ .env ---
if [ ! -f .env ]; then
    echo "No .env yet - creating one with a fresh JWT_SECRET."
    SECRET="$("$PY" -c 'import secrets; print(secrets.token_hex(32))')"
    cat > .env <<ENV
# Settings for the workshop app. This file is not committed to git.

# Pulse instructor password. CHANGE THIS before the workshop - students can
# reach the admin page too, they just cannot get in without it.
ADMIN_PASSWORD=cu2026

# Signs the instructor login. Generated once so restarting does not log you
# out. Keep it; a new one invalidates the session.
JWT_SECRET=$SECRET

# How long a login lasts, in hours.
JWT_HOURS=12

# The one port everything listens on.
PORT=8000

# Redis. If it is not running the app falls back to fakeredis by itself.
REDIS_URL=redis://localhost:6379/0
ENV
    echo "Created .env - open it and change ADMIN_PASSWORD."
    echo
fi

# Load every name in .env into the environment.
set -a
# shellcheck disable=SC1091
. ./.env
set +a

# --------------------------------------------------------------- checks ---
if ! "$PY" -c "import fastapi, uvicorn, redis, qrcode, jwt" 2>/dev/null; then
    echo "Some Python packages are missing. Install them with:" >&2
    echo "    $PY -m pip install -r requirements.txt" >&2
    exit 1
fi

if [ "${ADMIN_PASSWORD:-}" = "cu2026" ]; then
    echo "WARNING: ADMIN_PASSWORD is still the default 'cu2026'. Edit .env before the workshop."
    echo
fi

PORT_IN_USE="$(lsof -nP -iTCP:"${PORT:-8000}" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)"
if [ -n "$PORT_IN_USE" ]; then
    echo "Port ${PORT:-8000} is already being used by process $PORT_IN_USE." >&2
    echo "Stop it first, or set a different PORT in .env." >&2
    exit 1
fi

# ------------------------------------------------------------------ run ---
exec "$PY" main.py
