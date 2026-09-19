"""
Check that SkyBook and Pulse behave when they run together in one process.

    python smoke_test_all.py

The individual apps have their own tests; this one only covers the things that
can break by combining them - shared Redis, shared request log, shared port.
"""

import os
import pathlib
import signal
import subprocess
import sys
import time

import requests

HERE = pathlib.Path(__file__).parent
PORT = 8201
BASE = f"http://localhost:{PORT}"
ENV = dict(os.environ, PORT=str(PORT), PULSE_DB="/tmp/pulse_combined.db",
           JWT_SECRET="combined-smoke-secret-0123456789", ADMIN_PASSWORD="cu2026",
           REDIS_URL=os.environ.get("SMOKE_REDIS_URL", "redis://localhost:6379/12"))
passed = failed = 0


def check(label, ok, extra=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}   {extra}")


pathlib.Path("/tmp/pulse_combined.db").unlink(missing_ok=True)
server = subprocess.Popen([sys.executable, str(HERE / "main.py")], env=ENV,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for _ in range(80):
    try:
        if requests.get(BASE + "/health", timeout=1).ok:
            break
    except Exception:
        time.sleep(0.25)
else:
    raise SystemExit("combined server did not start:\n" + server.stdout.read())

print("\nSkyBook + Pulse, running together")

# ---- both apps answer on the one port --------------------------------------
print("\n-- one port, both apps")
check("/ is the index page", "AI Agents Workshop" in requests.get(BASE + "/").text)
check("/dashboard is SkyBook", "SkyBook" in requests.get(BASE + "/dashboard").text)
check("/quiz is Pulse", "PULSE" in requests.get(BASE + "/quiz").text)
check("/quiz/screen is the projector", "Scan to join" in requests.get(BASE + "/quiz/screen").text)
check("/health still answers", requests.get(BASE + "/health").json()["status"] == "ok")
openapi = requests.get(BASE + "/openapi.json").json()["paths"]
check("/docs covers SkyBook and Pulse",
      "/flights" in openapi and "/quiz/join" in openapi, str(len(openapi)) + " paths")

# ---- the join QR must point at the port we are really serving on ------------
screen = requests.get(BASE + "/quiz/screen").text
check(f"the QR join URL uses port {PORT}", f":{PORT}/quiz" in screen,
      screen[screen.find("JOIN_URL"):][:60])

# ---- set up data in both apps ----------------------------------------------
token = requests.post(BASE + "/quiz/admin/login", json={"password": "cu2026"}).json()["token"]
auth = {"Authorization": "Bearer " + token}
requests.post(BASE + "/quiz/admin/reset?scope=all", headers=auth)
student = requests.post(BASE + "/quiz/join", json={"name": "Aarav", "semester": "1st"}).json()
flight = requests.get(BASE + "/flights",
                      params={"source": "Chandigarh", "destination": "Goa"}).json()["flights"][0]
booking = requests.post(BASE + "/bookings", json={"flight_id": flight["flight_id"],
                                                  "passenger_name": "Aarav", "seats": 1}).json()

# ---- the dangerous one: one app's reset must not wipe the other -------------
print("\n-- the two resets stay in their own lane")
requests.post(BASE + "/reset")
check("SkyBook reset cleared its own bookings",
      requests.get(BASE + "/bookings").json()["count"] == 0)
check("SkyBook reset did NOT log the students out of Pulse",
      requests.get(BASE + "/quiz/state").json()["joined"] == 1)
check("SkyBook reset left the Pulse questions alone",
      len(requests.get(BASE + "/quiz/admin/questions", headers=auth).json()["questions"]) == 9)

requests.post(BASE + "/bookings", json={"flight_id": flight["flight_id"],
                                        "passenger_name": "Diya", "seats": 2})
requests.post(BASE + "/quiz/admin/reset?scope=all", headers=auth)
check("Pulse reset emptied its own roster", requests.get(BASE + "/quiz/state").json()["joined"] == 0)
check("Pulse reset did NOT delete the SkyBook bookings",
      requests.get(BASE + "/bookings").json()["count"] == 1)
check("Pulse reset left the SkyBook flights alone",
      requests.get(BASE + "/flights",
                   params={"source": "Chandigarh", "destination": "Goa"}).json()["count"] > 0)

# ---- Pulse polling must stay out of SkyBook's projected traffic panel -------
print("\n-- the projected API traffic panel")
for _ in range(12):
    requests.get(BASE + "/quiz/state")
requests.get(BASE + "/cities")
log = requests.get(BASE + "/api/dashboard").json()["log"]
check("Pulse polling is not in SkyBook's log", not any("/quiz" in line for line in log),
      str(log[:3]))
check("student agent traffic still is", any("/cities" in line for line in log), str(log[:3]))

server.send_signal(signal.SIGINT)
try:
    server.wait(timeout=10)
except subprocess.TimeoutExpired:
    server.kill()

print(f"\n  {passed} passed, {failed} failed\n")
sys.exit(1 if failed else 0)
