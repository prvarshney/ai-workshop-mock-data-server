"""
SkyBook - a tiny mock flight-booking API for the AI Agents workshop.

Run it with:  python mock_server.py
Then open:    http://localhost:8000/dashboard   (live dashboard)
              http://localhost:8000/docs        (Swagger, try the API by hand)

Runs on PORT (default 8000) - the same variable main.py and Pulse use.

Everything is stored in Redis. If Redis is not running we quietly fall back to
"fakeredis", an in-memory stand-in with the same commands, so the server always
starts. All the data is generated ONCE (with random.seed(42)) and then only read
back, so every student gets exactly the same flights and weather.
"""

import json
import os
import random
import socket
import string
import sys
from datetime import datetime
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

# --------------------------------------------------------------------------
# 1. Storage: real Redis if we can reach it, otherwise fakeredis
# --------------------------------------------------------------------------

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
PORT = int(os.environ.get("PORT", "8000"))   # one port for the whole workshop app


def connect_storage():
    """Return (client, name). Falls back to fakeredis when Redis is missing."""
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        return client, "redis"
    except Exception as exc:
        import fakeredis
        print(f"WARNING: cannot reach Redis at {REDIS_URL} ({exc.__class__.__name__}); "
              "using in-memory fakeredis instead - data is lost when the server stops.", flush=True)
        return fakeredis.FakeRedis(decode_responses=True), "fakeredis"


db, STORAGE = connect_storage()


def save_hash(key: str, obj: dict) -> None:
    """Write a dict as a Redis hash. Every value is JSON so types survive."""
    db.hset(key, mapping={k: json.dumps(v) for k, v in obj.items()})


# Redis hands hash fields back in no particular order, so we put them back in a
# fixed, readable order - that keeps every JSON response identical for everyone.
FIELD_ORDER = ["flight_id", "airline", "source", "destination", "departure_time",
               "duration_minutes", "price_inr", "seats_available",
               "city", "temperature_c", "feels_like_c", "condition", "humidity_percent",
               "wind_kmph", "visibility_km", "aqi", "sunrise", "sunset",
               "rain_chance_percent", "advice", "forecast",
               "pnr", "passenger_name", "seats", "total_price_inr", "status",
               "booked_at", "flight"]


def load_hash(key: str) -> Optional[dict]:
    """Read a Redis hash back into a dict, or None if the key is missing."""
    raw = db.hgetall(key)
    if not raw:
        return None
    keys = [k for k in FIELD_ORDER if k in raw] + [k for k in raw if k not in FIELD_ORDER]
    return {k: json.loads(raw[k]) for k in keys}


# --------------------------------------------------------------------------
# 2. The data we seed once
# --------------------------------------------------------------------------

CITIES = ["Chandigarh", "Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Chennai",
          "Kolkata", "Goa", "Jaipur", "Pune", "Lucknow", "Ahmedabad"]
CITY_LOOKUP = {c.lower(): c for c in CITIES}          # for case-insensitive matching

AIRLINES = [("IndiGo", "6E"), ("Air India", "AI"), ("Vistara", "UK"),
            ("Akasa Air", "QP"), ("SpiceJet", "SG")]

# Flights and weather use random.seed(42) so they are the same for everyone.
# PNRs use their own randomness instead, so they do not repeat after a /reset.
pnr_random = random.SystemRandom()

# Typical September weather per city: (condition, temp_c, humidity_%, aqi)
WEATHER_BASE = {
    "Chandigarh": ("Sunny", 33, 52, 115),
    "Delhi": ("Haze", 34, 62, 235),
    "Mumbai": ("Heavy rain", 29, 86, 88),
    "Bengaluru": ("Partly cloudy", 26, 68, 72),
    "Hyderabad": ("Cloudy", 29, 70, 95),
    "Chennai": ("Partly cloudy", 32, 76, 84),
    "Kolkata": ("Thunderstorm", 31, 82, 128),
    "Goa": ("Heavy rain", 28, 89, 54),
    "Jaipur": ("Sunny", 34, 48, 155),
    "Pune": ("Light rain", 27, 78, 80),
    "Lucknow": ("Haze", 33, 66, 205),
    "Ahmedabad": ("Sunny", 35, 50, 165),
}
RAIN_CHANCE = {"Sunny": 5, "Partly cloudy": 20, "Cloudy": 35, "Haze": 10,
               "Light rain": 65, "Heavy rain": 90, "Thunderstorm": 80}


def advice_for(condition: str, aqi: int) -> str:
    """One friendly line an agent can read out to the user."""
    if aqi > 200:
        return "Poor air, wear a mask"
    if condition in ("Light rain", "Heavy rain", "Thunderstorm"):
        return "Carry an umbrella"
    if condition == "Sunny":
        return "Wear sunscreen"
    if condition == "Haze":
        return "Hazy skies, avoid a long morning run"
    return "Pleasant, no special gear needed"


def route_key(src: str, dst: str) -> str:
    return f"flights:{src.upper()}:{dst.upper()}"


def seed() -> None:
    """Generate every flight and weather record. Deterministic thanks to seed(42)."""
    random.seed(42)

    used_ids = set()
    for src in CITIES:
        for dst in CITIES:
            if src == dst:
                continue
            ids = []
            for _ in range(4):                       # 4 flights per ordered city pair
                airline, code = random.choice(AIRLINES)
                while True:                          # keep drawing until the id is new
                    flight_id = code + str(random.randint(100, 999))
                    if flight_id not in used_ids:
                        used_ids.add(flight_id)
                        break
                save_hash("flight:" + flight_id, {
                    "flight_id": flight_id,
                    "airline": airline,
                    "source": src,
                    "destination": dst,
                    "departure_time": "%02d:%02d" % (random.randint(5, 22),
                                                     random.choice([0, 10, 15, 25, 30, 40, 45, 55])),
                    "duration_minutes": random.randint(60, 180),
                    "price_inr": random.randrange(2500, 9501, 100),
                    "seats_available": 500,          # plenty for 150 students - do not lower
                })
                ids.append(flight_id)
            db.rpush(route_key(src, dst), *ids)

    for city in CITIES:
        condition, temp, humidity, aqi = WEATHER_BASE[city]
        temp += random.randint(-1, 1)
        aqi = max(50, min(300, aqi + random.randint(-15, 15)))
        save_hash("weather:" + city.upper(), {
            "city": city,
            "temperature_c": temp,
            "feels_like_c": temp + random.randint(1, 5),
            "condition": condition,
            "humidity_percent": humidity + random.randint(-4, 4),
            "wind_kmph": random.randint(6, 26),
            "visibility_km": random.randint(1, 3) if condition == "Haze" else random.randint(5, 10),
            "aqi": aqi,
            "sunrise": "06:%02d" % random.randint(5, 25),
            "sunset": "18:%02d" % random.randint(20, 45),
            "rain_chance_percent": RAIN_CHANCE[condition],
            "advice": advice_for(condition, aqi),
            "forecast": [
                {"day": day,
                 "high_c": temp + random.randint(0, 3),
                 "low_c": temp - random.randint(4, 8),
                 "condition": random.choice([condition, "Partly cloudy", "Cloudy", "Light rain"])}
                for day in ("Tomorrow", "Day after", "In 3 days")
            ],
        })

    db.set("seeded", "1")


if not db.exists("seeded"):        # keep existing bookings if we restart mid-workshop
    seed()

# --------------------------------------------------------------------------
# 3. The API
# --------------------------------------------------------------------------

app = FastAPI(title="SkyBook Mock API",
              description="Flights, bookings and weather for the AI Agents workshop.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

QUIET_PATHS = {"/", "/dashboard", "/api/dashboard", "/docs", "/openapi.json",
               "/redoc", "/favicon.ico"}
# Pulse polls /quiz/state about 75 times a second; none of that belongs in the
# panel that is meant to show the students' agents calling SkyBook.
QUIET_PREFIXES = ("/quiz",)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Print and remember every student request so the dashboard can show it."""
    response = await call_next(request)
    path = request.url.path
    if path not in QUIET_PATHS and not path.startswith(QUIET_PREFIXES):
        query = "?" + request.url.query if request.url.query else ""
        line = (f"[{datetime.now().strftime('%H:%M:%S')}] {request.method} "
                f"{request.url.path}{query} -> {response.status_code}")
        print(line, flush=True)
        db.lpush("log", line)
        db.ltrim("log", 0, 29)
    return response


def resolve_city(name: str) -> str:
    """'  goa ' -> 'Goa'. Raises 404 listing the valid cities."""
    city = CITY_LOOKUP.get((name or "").strip().lower())
    if not city:
        raise HTTPException(404, f"Unknown city '{name}'. Known cities: {', '.join(CITIES)}")
    return city


@app.get("/health", tags=["flights"])
def health():
    return {"status": "ok", "storage": STORAGE, "server_time": datetime.now().strftime("%H:%M:%S")}


@app.get("/cities", tags=["flights"])
def list_cities():
    return {"cities": CITIES}


@app.get("/flights", tags=["flights"])
def search_flights(source: str, destination: str, max_price: Optional[int] = None):
    """Search flights on a route, cheapest first."""
    src, dst = resolve_city(source), resolve_city(destination)
    if src == dst:
        raise HTTPException(400, "source and destination must be different cities")
    flights = [load_hash("flight:" + fid) for fid in db.lrange(route_key(src, dst), 0, -1)]
    flights = [f for f in flights if f and f["seats_available"] > 0]
    if max_price is not None:
        flights = [f for f in flights if f["price_inr"] <= max_price]
    flights.sort(key=lambda f: (f["price_inr"], f["flight_id"]))
    return {"count": len(flights), "flights": flights}


@app.get("/flights/{flight_id}", tags=["flights"])
def get_flight(flight_id: str):
    flight = load_hash("flight:" + flight_id.strip().upper())
    if not flight:
        raise HTTPException(404, f"No flight with id '{flight_id}'")
    return flight


class BookingRequest(BaseModel):
    flight_id: str
    passenger_name: str
    seats: Any = 1          # Any, because small models often send "2" instead of 2


@app.post("/bookings", status_code=201, tags=["bookings"])
def create_booking(body: BookingRequest):
    """Book seats on a flight. Returns a PNR the agent can quote back."""
    try:
        seats = int(str(body.seats).strip())
    except (TypeError, ValueError):
        raise HTTPException(400, f"seats must be a number between 1 and 5, got '{body.seats}'")
    if not 1 <= seats <= 5:
        raise HTTPException(400, "seats must be between 1 and 5")
    name = body.passenger_name.strip()
    if not name:
        raise HTTPException(400, "passenger_name cannot be empty")

    key = "flight:" + body.flight_id.strip().upper()
    flight = load_hash(key)
    if not flight:
        raise HTTPException(404, f"No flight with id '{body.flight_id}'")

    left = db.hincrby(key, "seats_available", -seats)   # take the seats first...
    if left < 0:
        db.hincrby(key, "seats_available", seats)       # ...and give them back if oversold
        raise HTTPException(409, f"Only {left + seats} seat(s) left on {flight['flight_id']}")

    while True:                                         # 6-char PNR, e.g. 'K7M2QX'
        pnr = "".join(pnr_random.choices(string.ascii_uppercase + string.digits, k=6))
        if not db.exists("booking:" + pnr):
            break
    booking = {
        "pnr": pnr,
        "passenger_name": name,
        "seats": seats,
        "total_price_inr": flight["price_inr"] * seats,
        "status": "CONFIRMED",
        "booked_at": datetime.now().strftime("%H:%M:%S"),
        "flight": {k: flight[k] for k in
                   ("flight_id", "airline", "source", "destination", "departure_time")},
    }
    save_hash("booking:" + pnr, booking)
    db.lpush("bookings:all", pnr)
    return booking


@app.get("/bookings", tags=["bookings"])
def list_bookings():
    pnrs = db.lrange("bookings:all", 0, -1)
    bookings = [b for b in (load_hash("booking:" + p) for p in pnrs) if b]
    return {"count": len(bookings), "bookings": bookings}


@app.get("/bookings/{pnr}", tags=["bookings"])
def get_booking(pnr: str):
    booking = load_hash("booking:" + pnr.strip().upper())
    if not booking:
        raise HTTPException(404, f"No booking with PNR '{pnr}'")
    return booking


@app.delete("/bookings/{pnr}", tags=["bookings"])
def cancel_booking(pnr: str):
    key = "booking:" + pnr.strip().upper()
    booking = load_hash(key)
    if not booking:
        raise HTTPException(404, f"No booking with PNR '{pnr}'")
    if booking["status"] == "CANCELLED":
        raise HTTPException(409, f"Booking {booking['pnr']} is already cancelled")
    booking["status"] = "CANCELLED"
    save_hash(key, booking)
    db.hincrby("flight:" + booking["flight"]["flight_id"], "seats_available", booking["seats"])
    return booking


@app.get("/weather", tags=["weather"])
def weather(city: Optional[str] = None):
    """With ?city= give the full record, without it a one-line summary per city."""
    if city:
        return load_hash("weather:" + resolve_city(city).upper())
    summary = [load_hash("weather:" + c.upper()) for c in CITIES]
    return {"cities": [{"city": w["city"], "temperature_c": w["temperature_c"],
                        "condition": w["condition"]} for w in summary]}


@app.get("/weather/{city}", tags=["weather"])
def weather_by_path(city: str):
    return load_hash("weather:" + resolve_city(city).upper())


def clear_skybook():
    """Delete only SkyBook's own keys. Pulse shares this Redis database, so a
    FLUSHDB here would wipe every student's quiz answers."""
    for pattern in ("flight:*", "flights:*", "booking:*", "weather:*"):
        keys = list(db.scan_iter(match=pattern, count=500))
        if keys:
            db.delete(*keys)
    db.delete("bookings:all", "log", "seeded")


@app.post("/reset", tags=["skybook admin"])
def reset():
    """Wipe every booking and put all the seats back. Use between demos."""
    clear_skybook()
    seed()
    return {"status": "reset"}


@app.get("/api/dashboard", include_in_schema=False)
def dashboard_data():
    """Everything the big-screen dashboard needs, in one call."""
    pnrs = db.lrange("bookings:all", 0, 39)
    bookings = [b for b in (load_hash("booking:" + p) for p in pnrs) if b]
    all_bookings = [b for b in (load_hash("booking:" + p) for p in db.lrange("bookings:all", 0, -1)) if b]
    confirmed = [b for b in all_bookings if b["status"] == "CONFIRMED"]
    weather_strip = [load_hash("weather:" + c.upper()) for c in CITIES]
    return {
        "total": len(all_bookings),
        "confirmed": len(confirmed),
        "revenue": sum(b["total_price_inr"] for b in confirmed),
        "bookings": bookings,
        "log": db.lrange("log", 0, 29),
        "weather": [{"city": w["city"], "temperature_c": w["temperature_c"],
                     "condition": w["condition"]} for w in weather_strip],
    }


@app.get("/dashboard", include_in_schema=False, response_class=HTMLResponse)
def dashboard_page():
    return DASHBOARD_HTML


# --------------------------------------------------------------------------
# 4. The live dashboard (one self-contained page, no internet needed)
# --------------------------------------------------------------------------

DASHBOARD_HTML = """
<!doctype html><html><head><meta charset="utf-8"><title>SkyBook Live</title><style>
* { box-sizing: border-box; }
/* the whole page fills the screen exactly - nobody scrolls a projector */
body { margin:0; padding:24px; background:#1E1E1E; color:#E8ECF7; height:100vh; overflow:hidden;
       display:flex; flex-direction:column;
       font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
h1 { font-size:40px; margin:0 0 18px; letter-spacing:-0.5px; }
.stats { display:flex; gap:18px; margin-bottom:22px; }
.tile { flex:1; background:#2A2A2A; border-radius:14px; padding:18px 24px; }
.tile .label { color:#8B93AD; font-size:18px; text-transform:uppercase; letter-spacing:1px; }
.tile .value { font-size:56px; font-weight:800; color:#5AD1FF; line-height:1.1; }
.cols { display:flex; gap:18px; flex:1; min-height:0; }
.left { flex:2; } .right { flex:1; }
.left, .right { display:flex; flex-direction:column; min-height:0; }
.panel { background:#2A2A2A; border-radius:14px; padding:18px 22px; margin-bottom:18px;
         display:flex; flex-direction:column; min-height:0; }
.panel.grow { flex:1 1 0; min-height:0; }               /* API traffic takes all leftover space */
/* lists are clipped, never scrolled - the newest rows are at the top anyway */
/* the two lists scroll on their own - the page itself never scrolls */
#bookings, #log { overflow-y:auto; flex:1; padding-right:6px;
  scrollbar-width:thin; scrollbar-color:#4A5168 transparent; }
#bookings::-webkit-scrollbar, #log::-webkit-scrollbar { width:10px; }
#bookings::-webkit-scrollbar-thumb, #log::-webkit-scrollbar-thumb {
  background:#4A5168; border-radius:5px; }
#bookings::-webkit-scrollbar-thumb:hover, #log::-webkit-scrollbar-thumb:hover { background:#5AD1FF; }
.wxpanel { flex:0 0 auto; margin-bottom:0; }            /* weather takes only what it needs */
.panel h2 { font-size:24px; margin:0 0 14px; color:#8B93AD; text-transform:uppercase; letter-spacing:1px; }
.row { display:flex; justify-content:space-between; align-items:center; gap:16px;
       padding:14px 16px; border-radius:12px; background:#1E1E1E; margin-bottom:10px; }
.row.new { outline:3px solid #5AD1FF; animation: slide .45s ease-out; }
@keyframes slide { from { opacity:0; transform:translateY(-14px); } to { opacity:1; transform:none; } }
.row > div:first-child { min-width:0; }                 /* let long names shrink, not wrap */
.row > div:last-child { flex:0 0 auto; text-align:right; }
.name, .route, .meta { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.name { font-size:30px; font-weight:800; }
.route { font-size:24px; color:#E8ECF7; }
.meta { font-size:18px; color:#8B93AD; margin-top:2px; }
.pnr { font-family: ui-monospace, Menlo, Consolas, monospace; font-size:24px; color:#5AD1FF; }
.badge { font-size:17px; font-weight:800; padding:6px 12px; border-radius:999px; letter-spacing:1px; }
.CONFIRMED { color:#4ADE80; border:2px solid #4ADE80; }
.CANCELLED { color:#F87171; border:2px solid #F87171; }
.empty { font-size:28px; color:#8B93AD; padding:40px 0; text-align:center; }
.logline { font-family: ui-monospace, Menlo, Consolas, monospace; font-size:17px;
           color:#8B93AD; padding:3px 0; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.m { color:#5AD1FF; font-weight:700; } .ok { color:#4ADE80; } .err { color:#F87171; }
.wx { display:flex; flex-wrap:wrap; gap:6px; overflow:hidden; }
.wx div { background:#1E1E1E; border-radius:8px; padding:5px 10px; font-size:15px; white-space:nowrap; }
.wx b { color:#5AD1FF; font-size:17px; }
/* on a smaller projector everything shrinks a little so nothing wraps */
@media (max-width: 1400px) {
  h1 { font-size:32px; } .tile .value { font-size:42px; } .tile .label { font-size:15px; }
  .name { font-size:24px; } .route { font-size:19px; } .meta { font-size:15px; }
  .pnr { font-size:19px; } .logline { font-size:14px; } .panel h2 { font-size:19px; }
}
</style></head><body>
<h1>&#9992; SkyBook - live bookings from your agents</h1>
<div class="stats">
  <div class="tile"><div class="label">Bookings</div><div class="value" id="total">0</div></div>
  <div class="tile"><div class="label">Confirmed</div><div class="value" id="confirmed">0</div></div>
  <div class="tile"><div class="label">Revenue</div><div class="value" id="revenue">&#8377;0</div></div>
</div>
<div class="cols">
  <div class="left"><div class="panel grow"><h2>Latest bookings</h2><div id="bookings"></div></div></div>
  <div class="right">
    <div class="panel grow"><h2>API traffic</h2><div id="log"></div></div>
    <div class="panel wxpanel"><h2>Weather now</h2><div class="wx" id="weather"></div></div>
  </div>
</div>
<script>
const seen = new Set();                      // PNRs we have already shown once
const inr = n => "\\u20B9" + new Intl.NumberFormat("en-IN").format(n);   // 123400 -> 1,23,400
const esc = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

function bookingRow(b) {
  const isNew = !seen.has(b.pnr + b.status);
  seen.add(b.pnr + b.status);
  const f = b.flight;
  return `<div class="row ${isNew ? "new" : ""}">
    <div>
      <div class="name">${esc(b.passenger_name)}</div>
      <div class="route">${esc(f.source)} &rarr; ${esc(f.destination)}</div>
      <div class="meta">${esc(f.airline)} ${esc(f.flight_id)} &middot; ${esc(f.departure_time)} &middot; ${b.seats} seat(s)</div>
    </div>
    <div style="text-align:right">
      <div class="pnr">${esc(b.pnr)}</div>
      <div class="badge ${b.status}">${b.status}</div>
    </div></div>`;
}

function logRow(line) {                      // colour the method and the status code
  const status = (line.match(/-> (\\d{3})$/) || [])[1] || "";
  const cls = status.startsWith("2") ? "ok" : "err";
  return `<div class="logline">${esc(line)
    .replace(/(GET|POST|DELETE|PUT|PATCH)/, '<span class="m">$1</span>')
    .replace(/-&gt; (\\d{3})$/, `-> <span class="${cls}">$1</span>`)}</div>`;
}

// Redraw a list but stay where the reader scrolled to, instead of jumping to the top.
function draw(id, html) {
  const box = document.getElementById(id);
  const top = box.scrollTop;
  box.innerHTML = html;
  box.scrollTop = top;
}

async function refresh() {
  try {
    const d = await (await fetch("/api/dashboard")).json();
    total.textContent = d.total;
    confirmed.textContent = d.confirmed;
    revenue.textContent = inr(d.revenue);
    draw("bookings", d.bookings.length
      ? d.bookings.map(bookingRow).join("")
      : '<div class="empty">Waiting for the first agent to book a flight&hellip;</div>');
    draw("log", d.log.map(logRow).join("")
      || '<div class="logline">no requests yet</div>');
    document.getElementById("weather").innerHTML = d.weather
      .map(w => `<div><b>${esc(w.city)} ${w.temperature_c}&deg;</b> ${esc(w.condition)}</div>`).join("");
  } catch (e) { /* server restarting - just try again next tick */ }
}
refresh();
setInterval(refresh, 1500);
</script></body></html>
"""

# --------------------------------------------------------------------------
# 5. Start the server
# --------------------------------------------------------------------------

if __name__ == "__main__":
    # The workshop normally runs SkyBook and Pulse together on one port, so hand
    # over to main.py. Set SOLO=1 if you really want SkyBook by itself.
    _main = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    if not os.environ.get("SOLO") and os.path.exists(_main):
        print("Starting the whole workshop app (SkyBook + Pulse) via main.py."
              "\n  SOLO=1 python mock_server.py  runs SkyBook on its own.", flush=True)
        os.execv(sys.executable, [sys.executable, _main])

    # Only when SkyBook runs on its own - main.py serves its own index page here.
    app.get("/", include_in_schema=False)(lambda: RedirectResponse("/dashboard"))

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))           # no packet is sent, this just finds our LAN IP
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = "localhost"
    print("\n  SkyBook mock API"
          f"\n  storage    : {STORAGE}"
          f"\n  dashboard  : http://{lan_ip}:{PORT}/dashboard"
          f"\n  swagger    : http://{lan_ip}:{PORT}/docs"
          "\n  students use the address above (not localhost)\n", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
