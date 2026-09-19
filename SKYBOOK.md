# ✈ SkyBook — mock flight API for the AI Agents workshop

A tiny, offline, single-file API that student agents can call: search flights,
book seats, cancel, and check the weather. Everything the agents do shows up on
a live dashboard you can project on the big screen.

Nothing leaves the laptop — no API keys, no internet, no sign-up.

---

## 1. Install

```bash
pip install fastapi uvicorn redis fakeredis
```

Python 3.10 or newer (3.9 also works).

## 2. Run

```bash
python mock_server.py
```

To run SkyBook and Pulse together on one port instead, use
`python main.py` from the repo root — see the [project README](README.md).
This file covers SkyBook on its own.

You should see:

```
  SkyBook mock API
  storage    : redis
  dashboard  : http://192.168.1.41:8001/dashboard
  swagger    : http://192.168.1.41:8001/docs
  students use the address above (not localhost)
```

| URL | What it is |
| --- | --- |
| `http://<your-ip>:8001/dashboard` | Live dashboard — project this |
| `http://<your-ip>:8001/docs` | Swagger UI — click endpoints and try them live |
| `http://<your-ip>:8001/health` | Quick "is it up?" check |

## 3. Redis (optional)

SkyBook keeps its data in Redis. **If Redis is not running it automatically
falls back to `fakeredis`**, an in-memory stand-in, and prints a warning. The
API behaves exactly the same — the only difference is that data disappears when
you stop the server. For a workshop that is usually fine.

Use real Redis if you want bookings to survive a server restart.

| Platform | Command |
| --- | --- |
| macOS | `brew install redis` then `brew services start redis` |
| Docker (any OS) | `docker run -d -p 6379:6379 --name skybook-redis redis` |
| Windows | Install [Memurai](https://www.memurai.com/) (a Redis build for Windows), or use Docker / WSL |

Point somewhere else with an environment variable if you need to:

```bash
REDIS_URL=redis://localhost:6379/0 python mock_server.py
```

## 4. Tell students your IP address

Everyone must be on the same Wi-Fi. `localhost` only works on your own machine,
so give students the LAN address, e.g. `http://192.168.1.41:8001`.

| Platform | Command |
| --- | --- |
| macOS | `ipconfig getifaddr en0` (Wi-Fi) |
| Linux | `hostname -I` |
| Windows | `ipconfig` → look for "IPv4 Address" |

The server prints this address on startup too. If students cannot reach it,
it is almost always the laptop's firewall — allow incoming connections on
port 8001.

## 5. Endpoints

All responses are JSON. Errors look like `{"detail": "..."}`.

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/health` | `{"status":"ok","storage":"redis","server_time":"14:05:22"}` |
| GET | `/cities` | The 12 cities you can fly between |
| GET | `/flights?source=&destination=&max_price=` | Search a route, cheapest first. `max_price` optional. `404` unknown city, `400` if source == destination |
| GET | `/flights/{flight_id}` | One flight, e.g. `/flights/6E204`. `404` if unknown |
| POST | `/bookings` | Body `{"flight_id":"6E204","passenger_name":"Aarav","seats":2}` → `201` with a PNR. `404` unknown flight, `409` not enough seats |
| GET | `/bookings` | Every booking, newest first |
| GET | `/bookings/{pnr}` | One booking. PNR is case-insensitive |
| DELETE | `/bookings/{pnr}` | Cancel and put the seats back. `409` if already cancelled |
| GET | `/weather?city=Goa` | Full weather record for one city |
| GET | `/weather/{city}` | Same thing, as a path |
| GET | `/weather` | One-line summary for all 12 cities |
| POST | `/reset` | Delete every booking and re-seed. Use between demos |

Cities: Chandigarh, Delhi, Mumbai, Bengaluru, Hyderabad, Chennai, Kolkata,
Goa, Jaipur, Pune, Lucknow, Ahmedabad. City names are case-insensitive, so
`goa`, `Goa` and `  GOA ` all work.

### Try it from the terminal

```bash
curl "http://localhost:8001/flights?source=Chandigarh&destination=Goa"

curl -X POST http://localhost:8001/bookings \
  -H "Content-Type: application/json" \
  -d '{"flight_id":"SG723","passenger_name":"Aarav Sharma","seats":2}'

curl http://localhost:8001/weather/goa
```

## 6. Between demos

```bash
curl -X POST http://localhost:8001/reset
```

Wipes every booking, restores all seats to 500, and regenerates the same
flights and weather as before. The dashboard goes back to
"Waiting for the first agent to book a flight…" within 1.5 seconds.

## 7. Good to know

- **Everything is deterministic.** Flights and weather are generated once with
  `random.seed(42)`, so every student searching Chandigarh → Goa sees the same
  four flights at the same prices. Only bookings change anything.
- **500 seats per flight.** 150 students booking several times each will never
  sell out a popular route.
- **Restarting is safe.** With real Redis, stopping and restarting the server
  keeps every student's booking.
- **Small models send `"2"` instead of `2`.** The booking endpoint accepts a
  numeric string for `seats`, so llama3.2:3b does not trip over it.
- **The dashboard polls** `GET /api/dashboard` every 1.5 seconds. That request
  and the docs are hidden from the API traffic panel, so you only see student
  traffic.

## 8. Checking it works

```bash
pip install requests
python smoke_test.py                       # or: python smoke_test.py http://192.168.1.41:8001
```

26 checks covering determinism, booking, cancelling, seat restoration, error
codes and `/reset`.

Note: the smoke test calls `/reset`, so it wipes every booking on the server it
points at. Do not run it in the middle of the workshop.

## Files

| File | What it is |
| --- | --- |
| `mock_server.py` | The whole server: data, API and dashboard |
| `smoke_test.py` | End-to-end check |
| `README.md` | This file |
