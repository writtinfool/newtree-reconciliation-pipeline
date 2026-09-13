#!/usr/bin/env python3
"""
diagnose_places.py -- one-shot sanity check for PLACES_API_KEY.

Same idea as diagnose_pep.py: confirm the key actually works against a
couple of real, cheap calls before any real code (items 3 and 5 in
BACKLOG.md) gets built on top of it. Uses the new Places API (v1) --
Nearby Search and a single Place Details lookup -- against a known
coordinate (Slidell, LA, near 84 Inlet Dr) so results are easy to
eyeball. No API key is ever printed.

Usage:
    python3 diagnose_places.py
"""
import os
import json
import urllib.request
import urllib.error


def _load_dotenv(path=None):
    """Same tiny .env loader used by fetch_demographics.py / diagnose_pep.py."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

PLACES_API_KEY = os.environ.get("PLACES_API_KEY", "")

if not PLACES_API_KEY:
    print("PLACES_API_KEY is not set in .env. Add it next to CENSUS_API_KEY and re-run.")
    raise SystemExit(1)

print(f"Key length: {len(PLACES_API_KEY)} chars (not printing the value)\n")

# Known-good test point: near 84 Inlet Dr, Slidell, LA (lat/lng from prior
# geocoder runs), used only because we already know real commercial
# centers exist nearby to sanity-check results against.
TEST_LAT = 30.2672
TEST_LNG = -89.7812


def _post_json(url, payload, field_mask):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": PLACES_API_KEY,
            "X-Goog-FieldMask": field_mask,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


# Test 1: Nearby Search for "Home Depot" near the test point.
print("[TEST 1] Nearby Search -- home_improvement_store near test point")
try:
    body = {
        "includedTypes": ["home_improvement_store"],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": TEST_LAT, "longitude": TEST_LNG},
                "radius": 30000.0,  # 30km
            }
        },
    }
    result = _post_json(
        "https://places.googleapis.com/v1/places:searchNearby",
        body,
        "places.displayName,places.formattedAddress,places.location",
    )
    places = result.get("places", [])
    if places:
        print(f"[OK]   {len(places)} result(s):")
        for p in places[:5]:
            print(f"       - {p.get('displayName', {}).get('text')} -- {p.get('formattedAddress')}")
    else:
        print(f"[WARN] No results. Raw response: {json.dumps(result)[:300]}")
except urllib.error.HTTPError as e:
    print(f"[FAIL] HTTP {e.code} -- {e.read().decode()[:400]}")
except Exception as e:
    print(f"[FAIL] {e}")

print()

# Test 2: Text Search for a specific incorporated city name, to confirm
# the key also works for item 3's "find nearest incorporated city by
# name" step.
print("[TEST 2] Text Search -- 'Slidell, LA' (stand-in for nearest-city lookup)")
try:
    body = {"textQuery": "Slidell, LA"}
    result = _post_json(
        "https://places.googleapis.com/v1/places:searchText",
        body,
        "places.displayName,places.formattedAddress,places.location",
    )
    places = result.get("places", [])
    if places:
        print(f"[OK]   {len(places)} result(s):")
        for p in places[:3]:
            print(f"       - {p.get('displayName', {}).get('text')} -- {p.get('formattedAddress')}")
    else:
        print(f"[WARN] No results. Raw response: {json.dumps(result)[:300]}")
except urllib.error.HTTPError as e:
    print(f"[FAIL] HTTP {e.code} -- {e.read().decode()[:400]}")
except Exception as e:
    print(f"[FAIL] {e}")

print("\nDone. Paste this entire output back (no key is ever printed above).")