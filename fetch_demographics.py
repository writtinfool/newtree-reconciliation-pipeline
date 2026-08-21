#!/usr/bin/env python3
"""
fetch_demographics.py

Standalone module for the "Demographics & Economics" section of the
Investment Underwriting Brief pipeline. Designed to be imported by
reconcile.py as fetch_demographics(address) -> dict, or run standalone
for testing.

Data sources (all nationwide/standardized -- no per-county adapters needed):
  1. Census Geocoder    -- address -> state/county/place FIPS (no key required)
  2. Census ACS 5-Year   -- population, median household income, renter % (key required)
  3. Census PEP          -- population trend, county level (key required)
  4. BLS unemployment    -- county-level unemployment trend (no key required,
                             but rate-limited to 25 queries/day/IP without one)

USAGE:
    export CENSUS_API_KEY="your_key_here"
    python3 fetch_demographics.py "3511 Kent Dr, New Orleans, LA"

Get a free Census key (instant, no approval wait) at:
    https://api.census.gov/data/key_signup.html

Get a free BLS key (raises limit from 25/day to 500/day, 10yr to 20yr span) at:
    https://data.bls.gov/registrationEngine/

STATUS AS OF LAST BUILD (2026-08-21): county- and place-level population,
median household income, renter-occupied %, and unemployment trend are
implemented and CONFIRMED WORKING LIVE with a real Census API key against
84 Inlet Dr, Slidell, LA. Population trend is also confirmed working, but
via ACS 5-Year vintage comparison rather than the Census PEP dataset --
live diagnostic testing found PEP's 2020s-vintage data is not currently
reachable through the public API (2019 works, 2020-2024 do not; see the
NOTE near the top of this file). The nearest-city fallback chain
(incorporated place > CDP > mailing city > county subdivision) is also
confirmed working live -- correctly returns "Eden Isle" rather than the
meaningless voting-district name "District 12" for this address. Metro/CBSA
context, distance calculations, nearest-INCORPORATED-city lookup (via a
Places-tool search), commercial centers, and permit-office routing were
planned in detail but NOT implemented in this file -- see the companion
Demographics & Economics Module doc for the full backlog.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error

CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "")
BLS_API_KEY = os.environ.get("BLS_API_KEY", "")

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
ACS_URL_TMPL = "https://api.census.gov/data/{year}/acs/acs5"
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

ACS_YEAR = 2023          # latest available 5-year ACS release as of this build

# NOTE: pep/population (Census PEP dataset) is NOT currently used by this module.
# Live diagnostic testing on 2026-08-21 confirmed that, of vintages 2018-2024,
# only 2019 returns real data through this API; 2020, 2022, 2023, and 2024 all
# 404, and 2021 fails with a structural "unknown/unsupported geography hierarchy"
# error. This appears to be a genuine, current gap in Census's own API (their
# documentation states current PEP estimates aren't API-supported right now),
# not a bug in this code. get_population_trend() below uses ACS 5-Year vintage
# comparison instead, which is confirmed working. If PEP access is restored in
# the future, api.census.gov/data/{year}/pep/population is the right base URL
# to revisit -- re-run a diagnostic (see diagnose_pep.py) before trusting it again.


def _http_get_json(url, params=None):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "newtree-capital-brief/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def geocode_address(address):
    """
    address -> dict with state_fips, county_fips, place_fips (may be None if
    unincorporated), place_name, county_name, state_name, matched_address,
    is_incorporated (bool)
    """
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
    }
    data = _http_get_json(GEOCODER_URL, params)
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return {"error": f"No geocoder match for address: {address}"}

    m = matches[0]
    geos = m.get("geographies", {})
    state = (geos.get("States") or [{}])[0]
    county = (geos.get("Counties") or [{}])[0]
    place = (geos.get("Incorporated Places") or [{}])
    cdp = (geos.get("Census Designated Places") or [{}])
    cousub = (geos.get("County Subdivisions") or [{}])[0]

    is_incorporated = len(place) > 0 and place[0]
    place_info = place[0] if is_incorporated else {}
    # CDP (Census Designated Place, e.g. "Eden Isle CDP") is a real, recognizable
    # populated-place name for unincorporated areas -- much better fallback than
    # a county subdivision, which in Louisiana/some states is a voting ward or
    # police jury district ("District 12") with no public recognition value.
    cdp_info = cdp[0] if (len(cdp) > 0 and cdp[0]) else {}

    return {
        "matched_address": m.get("matchedAddress"),
        "state_fips": state.get("STATE"),
        "state_name": state.get("NAME"),
        "county_fips": county.get("COUNTY"),
        "county_name": county.get("NAME"),
        "place_fips": place_info.get("PLACE"),
        "place_name": place_info.get("NAME"),
        "is_incorporated": bool(is_incorporated),
        "cdp_name": cdp_info.get("BASENAME"),  # e.g. "Eden Isle" -- best fallback for unincorporated
        "county_subdivision_name": cousub.get("NAME"),  # last-resort fallback only
    }


def _nearest_city_name(geo, original_address=""):
    """
    Judgment-call rule for the brief's 'nearest city' field, in priority order:
      1. Incorporated place (e.g. "New Orleans city") -- no caveat, this is a real city.
      2. Census Designated Place / CDP (e.g. "Eden Isle") -- caveat that it's an
         unincorporated populated place, not a legal city.
      3. Mailing-address city as typed/matched (e.g. "Slidell" on 84 Inlet Dr, which
         is a USPS postal designation, not the property's actual municipality) --
         caveat that it's a postal designation only.
      4. County subdivision name -- last resort, since in some states (e.g. Louisiana
         police jury wards) this is a voting district with no public recognition value,
         so it is deliberately ranked below the mailing-city fallback.

    BUG HISTORY: the original version of this function used county_subdivision_name
    as the only fallback, which surfaced "District 12" (a Louisiana voting ward) as
    the "nearest city" for 84 Inlet Dr instead of the real, recognizable "Eden Isle."
    Fixed by adding the CDP and mailing-city tiers above county subdivision.
    """
    if geo.get("is_incorporated"):
        return {"name": geo["place_name"], "caveat": None}

    if geo.get("cdp_name"):
        return {
            "name": geo["cdp_name"],
            "caveat": "Property sits in an unincorporated Census-designated place, not "
                      "a legally incorporated city.",
        }

    # Try to pull the mailing city out of the original address string, e.g.
    # "84 Inlet Dr, Slidell, LA" -> "Slidell"
    mailing_city = None
    parts = [p.strip() for p in original_address.split(",")]
    if len(parts) >= 2:
        mailing_city = parts[1] if not any(ch.isdigit() for ch in parts[1]) else None
    if mailing_city:
        return {
            "name": mailing_city,
            "caveat": "Property is not within an incorporated city; this is the USPS "
                      "mailing-address city, a postal designation rather than a legal "
                      "municipal boundary.",
        }

    fallback = geo.get("county_subdivision_name")
    if fallback:
        return {
            "name": fallback,
            "caveat": "Property is not within an incorporated city; this is the nearest "
                      "administrative subdivision on file, not a legal city boundary.",
        }
    return {
        "name": None,
        "caveat": "Unable to determine a nearest-city reference for this unincorporated address.",
    }


def get_acs_data(state_fips, county_fips, place_fips=None):
    """
    Returns dict with population, median_household_income, renter_pct
    at both county level and place level (place level omitted if the
    address is unincorporated / has no place_fips).
    """
    if not CENSUS_API_KEY:
        return {"error": "CENSUS_API_KEY not set -- sign up free at "
                          "https://api.census.gov/data/key_signup.html"}

    variables = "NAME,B01003_001E,B19013_001E,B25003_001E,B25003_003E"
    # B01003_001E = total population
    # B19013_001E = median household income
    # B25003_001E = total occupied housing units
    # B25003_003E = renter-occupied housing units

    out = {}

    # County level
    try:
        county_data = _http_get_json(ACS_URL_TMPL.format(year=ACS_YEAR), {
            "get": variables,
            "for": f"county:{county_fips}",
            "in": f"state:{state_fips}",
            "key": CENSUS_API_KEY,
        })
        headers, row = county_data[0], county_data[1]
        rec = dict(zip(headers, row))
        total_occ = int(rec["B25003_001E"]) if rec["B25003_001E"] not in (None, "-666666666") else None
        renters = int(rec["B25003_003E"]) if rec["B25003_003E"] not in (None, "-666666666") else None
        out["county"] = {
            "name": rec["NAME"],
            "population": int(rec["B01003_001E"]),
            "median_household_income": int(rec["B19013_001E"]) if rec["B19013_001E"] not in (None, "-666666666") else None,
            "renter_occupied_pct": round(100 * renters / total_occ, 1) if total_occ and renters is not None else None,
        }
    except Exception as e:
        out["county"] = {"error": str(e)}

    # Place level (only if incorporated)
    if place_fips:
        try:
            place_data = _http_get_json(ACS_URL_TMPL.format(year=ACS_YEAR), {
                "get": variables,
                "for": f"place:{place_fips}",
                "in": f"state:{state_fips}",
                "key": CENSUS_API_KEY,
            })
            headers, row = place_data[0], place_data[1]
            rec = dict(zip(headers, row))
            total_occ = int(rec["B25003_001E"]) if rec["B25003_001E"] not in (None, "-666666666") else None
            renters = int(rec["B25003_003E"]) if rec["B25003_003E"] not in (None, "-666666666") else None
            out["place"] = {
                "name": rec["NAME"],
                "population": int(rec["B01003_001E"]),
                "median_household_income": int(rec["B19013_001E"]) if rec["B19013_001E"] not in (None, "-666666666") else None,
                "renter_occupied_pct": round(100 * renters / total_occ, 1) if total_occ and renters is not None else None,
            }
        except Exception as e:
            out["place"] = {"error": str(e)}

    out["acs_vintage"] = f"{ACS_YEAR} ACS 5-Year Estimates"
    return out


def get_population_trend(state_fips, county_fips):
    """
    County-level population trend, built by comparing two ACS 5-Year vintages
    rather than PEP.

    HISTORY OF THIS FUNCTION (all three attempts, so the next person doesn't
    repeat the investigation): the original version queried
    api.census.gov/data/{year}/pep/population once per calendar year, which
    doesn't match the modern PEP API's one-endpoint-per-vintage structure. A
    second version fixed that (querying a single vintage's full DATE_CODE
    time series) but still failed. Live diagnostic testing with a real key
    (2026-08-21) against St. Tammany Parish, LA nailed down why: of vintages
    2018-2024, only 2019 returned real data (HTTP 200); 2021 failed with a
    DIFFERENT error ("unknown/unsupported geography hierarchy" -- a
    structural change, not just missing data); 2020, 2022, 2023, and 2024
    all 404'd outright. This means the entire 2020s-vintage PEP system
    appears to be genuinely unpublished/broken via this API right now --
    consistent with Census's own documentation stating "Current estimates
    are unable to be supported by the API at this time." This is a gap on
    Census's end, not a bug in this code, and chasing it further was not
    worth it once ACS was confirmed to work reliably across the same years.

    FIX: build the trend from ACS 5-Year population totals at two vintages
    instead -- confirmed live that vintages 2018 through 2023 are all
    reachable. This trades PEP's annual point-estimates for ACS's rolling
    5-year averages, which is a real precision tradeoff worth knowing about
    (see the note in the returned dict), but it works today, and it reuses
    the exact same ACS call already proven functional for the main
    population/income/renter-% figures.
    """
    if not CENSUS_API_KEY:
        return {"error": "CENSUS_API_KEY not set"}

    EARLY_VINTAGE = 2018
    LATE_VINTAGE = ACS_YEAR  # currently 2023, kept in sync with the main ACS call

    def _pull(vintage):
        data = _http_get_json(ACS_URL_TMPL.format(year=vintage), {
            "get": "NAME,B01003_001E",
            "for": f"county:{county_fips}",
            "in": f"state:{state_fips}",
            "key": CENSUS_API_KEY,
        })
        headers, row = data[0], data[1]
        rec = dict(zip(headers, row))
        return int(rec["B01003_001E"])

    try:
        early_pop = _pull(EARLY_VINTAGE)
    except Exception as e:
        return {"error": f"ACS pull failed for {EARLY_VINTAGE} vintage: {e}"}

    try:
        late_pop = _pull(LATE_VINTAGE)
    except Exception as e:
        return {"error": f"ACS pull failed for {LATE_VINTAGE} vintage: {e}"}

    pct_change = round(100 * (late_pop - early_pop) / early_pop, 1) if early_pop else None

    return {
        "early_vintage": f"{EARLY_VINTAGE} ACS 5-Year (5-yr rolling avg centered on {EARLY_VINTAGE})",
        "early_population": early_pop,
        "late_vintage": f"{LATE_VINTAGE} ACS 5-Year (5-yr rolling avg centered on {LATE_VINTAGE})",
        "late_population": late_pop,
        "pct_change": pct_change,
        "direction": "growing" if pct_change and pct_change > 0.5 else (
            "declining" if pct_change and pct_change < -0.5 else "roughly flat"
        ),
        "note": "Built from ACS 5-Year rolling-average population, not PEP annual point estimates -- "
                "PEP's 2020s data is currently unpublished/unreachable via the Census API (confirmed via "
                "live diagnostic testing, not assumed). ACS 5-year figures smooth over short-term swings, "
                "so this trend understates year-to-year volatility compared to what PEP would show if it "
                "were available. Re-check periodically whether PEP's API access has been restored.",
    }


def get_bls_unemployment_trend(state_fips, county_fips):
    """
    County unemployment trend via BLS LAUS series.
    Series ID format: LAUCN + state(2) + county(3) + 0000000003 (unemployment rate)
    """
    series_id = f"LAUCN{state_fips}{county_fips}0000000003"
    payload = {"seriesid": [series_id], "startyear": "2021", "endyear": "2025"}
    if BLS_API_KEY:
        payload["registrationkey"] = BLS_API_KEY

    req = urllib.request.Request(
        BLS_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

    if data.get("status") != "REQUEST_SUCCEEDED":
        return {"error": data.get("message", "BLS request failed")}

    series = data.get("Results", {}).get("series", [{}])[0].get("data", [])
    # period is "M01".."M12" -- sort on (year, period), not periodName. periodName is
    # alphabetical ("December" < "November"), which produced a wrong "latest" point
    # in the first version of this function -- fixed here.
    points = [(d["year"], d["period"], d["periodName"], d["value"]) for d in series if d["value"] != "-"]
    points.sort(key=lambda p: (p[0], p[1]))  # chronological: year asc, then M01..M12 asc

    if not points:
        return {"error": "No usable BLS data points returned"}

    latest = points[-1]
    year_ago = next((p for p in points if p[0] == str(int(latest[0]) - 1) and p[1] == latest[1]), None)

    return {
        "latest": {"period": f"{latest[2]} {latest[0]}", "rate_pct": float(latest[3])},
        "year_ago": {"period": f"{year_ago[2]} {year_ago[0]}", "rate_pct": float(year_ago[3])} if year_ago else None,
        "series_id": series_id,
        "note": "BLS Local Area Unemployment Statistics (LAUS), county level, not seasonally adjusted.",
    }


def fetch_demographics(address):
    """
    Main entry point. Call this from reconcile.py.
    Returns a dict ready to attach as reconciled_json['demographics_economics'].
    """
    geo = geocode_address(address)
    if geo.get("error"):
        return {"error": geo["error"]}

    result = {
        "geocode": geo,
        "nearest_city": _nearest_city_name(geo, address),
    }

    if geo.get("state_fips") and geo.get("county_fips"):
        result["acs"] = get_acs_data(geo["state_fips"], geo["county_fips"], geo.get("place_fips"))
        result["population_trend_county"] = get_population_trend(geo["state_fips"], geo["county_fips"])
        result["unemployment_trend_county"] = get_bls_unemployment_trend(geo["state_fips"], geo["county_fips"])
    else:
        result["error"] = "Geocoder did not return state/county FIPS -- cannot pull ACS/PEP/BLS data."

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 fetch_demographics.py \"<full address>\"")
        sys.exit(1)
    addr = sys.argv[1]
    out = fetch_demographics(addr)
    print(json.dumps(out, indent=2))