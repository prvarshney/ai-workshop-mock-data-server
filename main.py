"""
The whole workshop in one command.

    python main.py

Starts both apps on one port, so there is a single address to write on the
board and a single firewall prompt to accept:

    /            this index page
    /dashboard   SkyBook - live bookings from the students' agents
    /quiz        Pulse - the audience quiz, on phones
    /docs        the API docs for both

Run either app on its own instead with `python mock_server.py` or
`python pulse/pulse.py` - they still work standalone.
"""

import os

import uvicorn
from fastapi.responses import HTMLResponse

import mock_server                     # SkyBook: creates its app and seeds flights
import pulse.pulse as pulse_app         # Pulse: exposes a router we can mount
import pulse.auth as pulse_auth
import pulse.storage as pulse_storage

PORT = int(os.environ.get("PORT", os.environ.get("PULSE_PORT", "8000")))

# Pulse builds its join QR code from its own port number. We are serving it on
# OUR port, so tell it the truth - otherwise every scanned QR points nowhere.
pulse_app.PORT = PORT
LAN_IP = pulse_app.LAN_IP

app = mock_server.app                   # reuse SkyBook's app: CORS and the request log
app.title = "Workshop - SkyBook + Pulse"
app.include_router(pulse_app.router, prefix="/quiz")

INDEX = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Agents Workshop</title><style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:#1E1E1E;color:#E8ECF7;padding:40px;
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  display:flex;flex-direction:column;justify-content:center}
h1{font-size:40px;margin:0 0 6px}
p.sub{color:#8B93AD;font-size:20px;margin:0 0 34px}
.wrap{width:100%;max-width:1150px;margin:0 auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}
a.tile{display:block;background:#2A2A2A;border-radius:16px;padding:24px;text-decoration:none;
  color:#E8ECF7;border:2px solid transparent;transition:border-color .15s}
a.tile:hover{border-color:#5AD1FF}
.tile b{display:block;font-size:26px;color:#5AD1FF;margin-bottom:6px}
.tile span{color:#8B93AD;font-size:17px;line-height:1.4;display:block}
.tile code{color:#E8ECF7;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:15px}
footer{margin-top:34px;color:#8B93AD;font-size:16px}
</style></head><body>
<div class="wrap">
<h1>AI Agents Workshop</h1>
<p class="sub">Chandigarh University &middot; everything runs on this laptop</p>
<div class="grid">
  <a class="tile" href="/quiz"><b>Pulse &mdash; join the quiz</b>
    <span>Students open this on their phones<br><code>/quiz</code></span></a>
  <a class="tile" href="/quiz/screen"><b>Pulse &mdash; projector</b>
    <span>Shows the QR code, then the live results<br><code>/quiz/screen</code></span></a>
  <a class="tile" href="/quiz/admin"><b>Pulse &mdash; control panel</b>
    <span>Launch questions, reveal answers, export<br><code>/quiz/admin</code></span></a>
  <a class="tile" href="/dashboard"><b>SkyBook &mdash; live bookings</b>
    <span>What the students' agents are booking<br><code>/dashboard</code></span></a>
  <a class="tile" href="/docs"><b>API docs</b>
    <span>Swagger for SkyBook and Pulse together<br><code>/docs</code></span></a>
  <a class="tile" href="/health"><b>Health check</b>
    <span>Is it up, and which storage is it using<br><code>/health</code></span></a>
</div>
<footer>Students use the address shown on the projector, not localhost.</footer>
</div>
</body></html>
"""


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def index():
    return INDEX


if __name__ == "__main__":
    where = LAN_IP or "localhost"
    secret = ("from JWT_SECRET" if pulse_auth.SECRET_FROM_ENV
              else "generated now (set JWT_SECRET to stay logged in across restarts)")
    print(f"\n  AI Agents Workshop - SkyBook + Pulse"
          f"\n  skybook storage : {mock_server.STORAGE}"
          f"\n  pulse storage   : {pulse_storage.STORAGE}"
          f"\n  questions       : {pulse_storage.DB_PATH}"
          f"\n  jwt secret      : {secret}"
          + ("" if pulse_auth.SECRET_FROM_ENV else f"\n                    JWT_SECRET={pulse_auth.JWT_SECRET}")
          + f"\n\n  index      : http://{where}:{PORT}/"
          f"\n  students   : http://{where}:{PORT}/quiz"
          f"\n  projector  : http://{where}:{PORT}/quiz/screen"
          f"\n  instructor : http://{where}:{PORT}/quiz/admin"
          f"\n  skybook    : http://{where}:{PORT}/dashboard"
          f"\n  api docs   : http://{where}:{PORT}/docs"
          f"\n\n  students use the address above, not localhost\n", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
