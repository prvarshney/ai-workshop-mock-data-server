"""Quick end-to-end check of the SkyBook API. Start mock_server.py first, then:
   python smoke_test.py"""
import json
import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
passed = failed = 0


def check(label, ok, extra=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label} {extra}")


def get(path, **kw):
    return requests.get(BASE + path, timeout=10, **kw)


print("\nSkyBook smoke test against", BASE)
print("NOTE: this wipes every booking on that server (it calls /reset).")

# 0. start from a clean slate so the checks below do not depend on earlier bookings
requests.post(BASE + "/reset", timeout=10)

# 1. health
r = get("/health")
check("/health is ok", r.status_code == 200 and r.json()["status"] == "ok", r.text)
print("        storage backend:", r.json()["storage"])

# 2. the same search twice must be byte-identical
a = get("/flights", params={"source": "chandigarh", "destination": " Goa "})
b = get("/flights", params={"source": "CHANDIGARH", "destination": "goa"})
check("Chandigarh->Goa search is deterministic", a.text == b.text)
check("search returned flights, cheapest first",
      a.json()["count"] > 0 and a.json()["flights"] == sorted(
          a.json()["flights"], key=lambda f: (f["price_inr"], f["flight_id"])))

# 3. weather is deterministic too
w1, w2 = get("/weather/goa"), get("/weather/goa")
check("/weather/goa is deterministic", w1.text == w2.text)
check("/weather/goa has advice + 3-day forecast",
      "advice" in w1.json() and len(w1.json()["forecast"]) == 3)

# 4. error handling
check("unknown city -> 404", get("/flights", params={"source": "Paris", "destination": "Goa"}).status_code == 404)
check("same city -> 400", get("/flights", params={"source": "Goa", "destination": "goa"}).status_code == 400)
check("unknown flight -> 404", get("/flights/ZZ999").status_code == 404)

# 5. book the cheapest flight
cheapest = a.json()["flights"][0]
before = get("/flights/" + cheapest["flight_id"]).json()["seats_available"]
r = requests.post(BASE + "/bookings", json={"flight_id": cheapest["flight_id"],
                                            "passenger_name": "Aarav Sharma", "seats": 2}, timeout=10)
check("POST /bookings -> 201", r.status_code == 201, r.text)
booking = r.json()
check("PNR is 6 chars", len(booking["pnr"]) == 6 and booking["pnr"].isalnum())
check("total price = price x seats", booking["total_price_inr"] == cheapest["price_inr"] * 2)
check("seats were taken", get("/flights/" + cheapest["flight_id"]).json()["seats_available"] == before - 2)

# 6. fetch it back (lowercase PNR on purpose)
r = get("/bookings/" + booking["pnr"].lower())
check("GET /bookings/{pnr} is case-insensitive", r.status_code == 200 and r.json()["pnr"] == booking["pnr"])
check("booking appears in the list", booking["pnr"] in [x["pnr"] for x in get("/bookings").json()["bookings"]])

# 7. cancel it and check the seats come back
r = requests.delete(BASE + "/bookings/" + booking["pnr"], timeout=10)
check("DELETE -> CANCELLED", r.status_code == 200 and r.json()["status"] == "CANCELLED", r.text)
check("seats restored", get("/flights/" + cheapest["flight_id"]).json()["seats_available"] == before)
check("cancelling twice -> 409",
      requests.delete(BASE + "/bookings/" + booking["pnr"], timeout=10).status_code == 409)

# 8. small LLMs send seats as a string
r = requests.post(BASE + "/bookings", json={"flight_id": cheapest["flight_id"],
                                            "passenger_name": "Diya Patel", "seats": "2"}, timeout=10)
check('seats "2" as a string works', r.status_code == 201 and r.json()["seats"] == 2, r.text)
check("seats out of range -> 400",
      requests.post(BASE + "/bookings", json={"flight_id": cheapest["flight_id"],
                                              "passenger_name": "X", "seats": 9}, timeout=10).status_code == 400)

# 9. reset wipes bookings and puts the seats back
r = requests.post(BASE + "/reset", timeout=10)
check("POST /reset -> reset", r.status_code == 200 and r.json()["status"] == "reset", r.text)
check("no bookings after reset", get("/bookings").json()["count"] == 0)
check("seats back to 500", get("/flights/" + cheapest["flight_id"]).json()["seats_available"] == 500)
check("data identical after re-seed", get("/flights", params={"source": "chandigarh",
                                                              "destination": "goa"}).text == a.text)

# 10. dashboard feed
d = get("/api/dashboard").json()
check("/api/dashboard has all its panels",
      {"total", "confirmed", "revenue", "bookings", "log", "weather"} <= set(d))
check("dashboard page renders", get("/").status_code == 200 and "SkyBook" in get("/").text)
check("/docs still works", get("/docs").status_code == 200)

print(f"\n  {passed} passed, {failed} failed\n")
sys.exit(1 if failed else 0)
