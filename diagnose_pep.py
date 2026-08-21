#!/usr/bin/env python3
"""
diagnose_pep.py -- one-shot diagnostic for the PEP population-trend failure.

Tests several variable combinations and geography levels against several
vintages, using your real CENSUS_API_KEY, and reports exactly which
combination(s) actually return data. Run this once; paste the FULL output
back (no API key is ever printed).

Usage:
    python3 diagnose_pep.py
"""
import os
import json
import urllib.request
import urllib.parse
import urllib.error

CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "")

if not CENSUS_API_KEY:
    print("CENSUS_API_KEY is not set in this session. Set it first, same as before.")
    raise SystemExit(1)

STATE_FIPS = "22"    # Louisiana
COUNTY_FIPS = "103"  # St. Tammany Parish

TESTS = [
    ("2024, NAME+POP only", "2024", "NAME,POP"),
    ("2023, NAME+POP only", "2023", "NAME,POP"),
    ("2022, NAME+POP only", "2022", "NAME,POP"),
    ("2021, NAME+POP only", "2021", "NAME,POP"),
    ("2020, NAME+POP only", "2020", "NAME,POP"),
    ("2019, NAME+POP only", "2019", "NAME,POP"),
    ("2018, NAME+POP only", "2018", "NAME,POP"),
]

print(f"Testing against St. Tammany Parish, LA (state={STATE_FIPS}, county={COUNTY_FIPS})")
print(f"Key length: {len(CENSUS_API_KEY)} chars (not printing the value)\n")

for label, year, get_vars in TESTS:
    url = f"https://api.census.gov/data/{year}/pep/population"
    params = {
        "get": get_vars,
        "for": f"county:{COUNTY_FIPS}",
        "in": f"state:{STATE_FIPS}",
        "key": CENSUS_API_KEY,
    }
    full_url = url + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "diagnose-pep/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
        print(f"[OK]   {label}")
        print(f"       -> {body[:300]}")
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode()[:300]
        except Exception:
            pass
        print(f"[FAIL] {label} -- HTTP {e.code}")
        if error_body:
            print(f"       -> {error_body}")
    except Exception as e:
        print(f"[FAIL] {label} -- {e}")
    print()

print("Done. Paste this entire output back.")