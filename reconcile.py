#!/usr/bin/env python3
"""
Newtree Capital — Property Data Reconciliation Tool
=====================================================

Reconciles three recurring data sources into a single trusted record,
flags conflicts, and screens contact data for outbound-calling compliance.

SOURCES SUPPORTED
  1. Property Profile Report   (SendFuse / TitleToolbox / Benutech)  -- .pdf
  2. Comparable Sales Report   (Dealio.pro)                          -- .pdf
  3. Skip-trace lead export    (LPP-style export)                    -- .csv

TRUST HIERARCHY (highest wins on conflict)
  1. Manual public-record override   (assessor site / MLS / county clerk —
     entered by a human after a quick lookup; see --public-override)
  2. Comps Report + CSV pairing      (these two have, in practice, come from
     the same underlying data pipeline and corroborate each other)
  3. Property Profile Report         (title-company pull; has shown material
     errors on physical characteristics and loan attribution)

USAGE
  python3 reconcile.py \
      --profile "3511_Kent_Dr...PropertyProfile.pdf" \
      --comps "Comps_Report-17.pdf" \
      --csv "lpp-export-....csv" \
      --public-override public_override.json \
      --out reconciled_3511_Kent_Dr.json

  Any of --profile / --comps / --csv / --public-override may be omitted if
  that source isn't available for a given property — the tool reconciles
  with whatever it's given and notes what's missing.
"""

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from fetch_demographics import fetch_demographics
except ImportError:
    fetch_demographics = None  # demographics section skipped if module isn't alongside this script

try:
    import pdfplumber
except ImportError:
    print("pdfplumber is required: pip install pdfplumber --break-system-packages", file=sys.stderr)
    raise


# --------------------------------------------------------------------------
# Parsing: Property Profile Report (SendFuse / TitleToolbox / Benutech)
# --------------------------------------------------------------------------

def parse_property_profile(path):
    """Extract key fields from a SendFuse/TitleToolbox Property Profile Report."""
    with pdfplumber.open(path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    data = {"source": "property_profile", "file": str(path)}

    def grab(pattern, text=full_text, cast=str):
        m = re.search(pattern, text)
        if not m:
            return None
        val = m.group(1).strip()
        try:
            return cast(val)
        except (ValueError, TypeError):
            return val

    data["owner_name"] = grab(r"Primary Owner:\s*([A-Z ,.'-]+?)\s+APN:")
    data["apn"] = grab(r"APN:\s*([\d-]+)")
    data["site_address"] = grab(r"Site Address:\s*([^\n]+)")
    # NOTE: this report's "Year Built / Effective Year Built:" label wraps
    # across the PDF layout such that a naive "label...:" regex can grab an
    # unrelated 4-digit number (e.g. from "Acres: 6300"). This format always
    # renders effective year as a "0000" placeholder immediately after the
    # real year, so anchor on that instead.
    data["year_built"] = grab(r"(\d{4})\s*/\s*0000", cast=int)
    data["lot_sqft"] = grab(r"Lot sqft\s*/\s*Acres:\s*([\d,]+)",
                             cast=lambda v: int(v.replace(",", "")))
    data["bedrooms"] = grab(r"Bedrooms:\s*(\d+)", cast=int)
    data["square_feet"] = grab(r"Square Feet:\s*([\d,]+)",
                                cast=lambda v: int(v.replace(",", "")))
    data["bathrooms"] = grab(r"Total Bathrooms:\s*([\d.]+)", cast=float)
    data["assessed_value"] = grab(r"Assessed Value:\s*\$([\d,]+)",
                                   cast=lambda v: int(v.replace(",", "")))
    data["tax_amount"] = grab(r"Tax Amount:\s*\$([\d,]+)",
                               cast=lambda v: int(v.replace(",", "")))
    data["market_value_reported"] = grab(r"Market Value:\s*\$([\d,]+)",
                                          cast=lambda v: int(v.replace(",", "")))
    data["percent_improvement"] = grab(r"Percent Improvement:\s*([\d.]+)%", cast=float)

    # Sale / transfer
    data["transfer_date"] = grab(r"Transfer Date:\s*([\d-]+)")
    data["transfer_value"] = grab(r"Transfer Value:\s*\$?([\d,]+)",
                                   cast=lambda v: int(v.replace(",", "")))

    # Mortgage block (may not exist)
    mort = re.search(
        r"MORTGAGE\s+Recording Date:\s*([^\n]+?)\s+Loan Amount:\s*\$\s*([\d,\.]+)"
        r".*?Lender Name:\s*([^\n]+?)\s*\n"
        r"Borrower Name\(s\):\s*([^\n]+?)\s+Doc #:",
        full_text, re.S,
    )
    if mort:
        data["mortgage"] = {
            "recording_date": mort.group(1).strip(),
            "loan_amount": float(mort.group(2).replace(",", "")),
            "lender_name": mort.group(3).strip(),
            "borrower_names": mort.group(4).strip(),
        }
    else:
        data["mortgage"] = None

    # "CURRENT MORTGAGE RECORD" block -- separate from the historical MORTGAGE
    # block above. This report format has shown a real bug: it sometimes
    # labels a prior owner's old, already-superseded loan as "current."
    cur_mort = re.search(
        r"CURRENT MORTGAGE RECORD\s+Recording Date:\s*([^\n]+?)\s+Loan Amount:\s*\$\s*([\d,\.]+)"
        r".*?Lender Name:\s*([^\n]+?)\s*\n"
        r"Borrower Name\(s\):\s*([^\n]+?)\s+Doc #:",
        full_text, re.S,
    )
    data["current_mortgage_record"] = None
    if cur_mort:
        data["current_mortgage_record"] = {
            "recording_date": cur_mort.group(1).strip(),
            "loan_amount": float(cur_mort.group(2).replace(",", "")),
            "lender_name": cur_mort.group(3).strip(),
            "borrower_names": cur_mort.group(4).strip(),
        }

    # Purchase-section seller (the party who sold TO the current owner) and
    # any recorded release of the purchase-money mortgage.
    data["purchase_seller"] = grab(r"Seller Name\(s\):\s*([^\n]+?),?\s*--")
    release = re.search(r"Release Date:\s*([^\n]+?)\s+Release Doc:\s*([^\n]+)", full_text)
    if release:
        data["mortgage_release"] = {"date": release.group(1).strip(), "doc": release.group(2).strip()}
    else:
        data["mortgage_release"] = None
    data["purchase_first_td"] = grab(r"First TD:\s*\$\s*([\d,\.]+)",
                                      cast=lambda v: float(v.replace(",", "")))
    data["purchase_lender"] = grab(r"Mortgage Doc #:.*?\n?Lender:\s*([^\n]+)")

    return data


# --------------------------------------------------------------------------
# Parsing: Comps Report (Dealio.pro)
# --------------------------------------------------------------------------

def parse_comps_report(path):
    """Extract key fields from a Dealio.pro Comparable Sales Report, including
    the full comp list (all pages) for ARV computation."""
    with pdfplumber.open(path) as pdf:
        page1_text = pdf.pages[0].extract_text() or ""
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    data = {"source": "comps_report", "file": str(path)}

    def grab(pattern, text=page1_text, cast=str):
        m = re.search(pattern, text)
        if not m:
            return None
        val = m.group(1).strip()
        try:
            return cast(val)
        except (ValueError, TypeError):
            return val

    data["subject_address"] = grab(r"Subject Property\s*\n([^\n]+)\n([^\n]+)")
    data["bedrooms"] = grab(r"Bed\s+(\d+)", cast=int)
    data["bathrooms"] = grab(r"Bath\s+([\d.]+)", cast=float)
    data["stories"] = grab(r"Stories\s+([\d.]+)", cast=float)
    data["square_feet"] = grab(r"Square Feet\s+([\d,]+)",
                                cast=lambda v: int(v.replace(",", "")))
    data["lot_size_sqft"] = grab(r"Lot Size\s+([\d,]+)\s*sqft",
                                  cast=lambda v: int(v.replace(",", "")))
    data["year_built"] = grab(r"Year Built\s+(\d{4})", cast=int)

    sale = re.search(r"Last Sold\s+\$([\d,]+)\s*\(([\d/]+)\)", page1_text)
    if sale:
        data["last_sold_price"] = int(sale.group(1).replace(",", ""))
        data["last_sold_date"] = sale.group(2)
    else:
        data["last_sold_price"] = None
        data["last_sold_date"] = None

    data["estimated_value"] = grab(r"Estimated Value\s*\*\s*\$([\d,]+)",
                                    cast=lambda v: int(v.replace(",", "")))
    data["avm"] = grab(r"AVM\s+\$([\d,]+)", cast=lambda v: int(v.replace(",", "")))
    data["ltv_percent"] = grab(r"Loan to Value\s+(\d+)%", cast=int)
    data["wholesale_score"] = grab(r"Wholesale Score\s+(\d+)", cast=int)
    data["retail_score"] = grab(r"Retail Score\s+(\d+)", cast=int)
    data["rental_score"] = grab(r"Rental Score\s+(\d+)", cast=int)

    # --- Full comp list, all pages, for ARV computation --------------------
    data["comps"] = _parse_comp_table(full_text)

    return data


def _parse_comp_table(full_text):
    """
    Parses the multi-page "Comparable List" table. Each page block has a
    Subject column plus 2-3 comp columns, laid out as parallel label rows
    (e.g. "Bed 5 4 4 4" = subject, comp1, comp2, comp3).

    ARV basis: prefer the comp's Listing Price as the $/sqft basis (matches
    the report's own "Basis" language distinguishing true closed sales from
    listing-price proxies); a comp only counts as a "confirmed closed sale"
    when its Last Sold price is present AND differs from its Listing Price
    (i.e. Last Sold isn't just an echo of the current listing).
    Deduplicates identical (sqft, price, status) rows, since this report
    format has been observed to repeat the same comp values within a block.
    """
    blocks = full_text.split("Comparable List")[1:]
    raw = []
    for block in blocks:
        row = {}
        for line in block.split("\n"):
            line = line.strip()
            m = re.match(r"^(Bed|Bath|Square Feet|Listing Price|Last Sold|Listing Status)\s+(.*)$", line)
            if m:
                label, rest = m.groups()
                row.setdefault(label, rest)

        sqft_nums = [int(x.replace(",", "")) for x in
                     re.findall(r"([\d,]+)\s*(?:Δ\s*[+-]?[\d,]+)?", row.get("Square Feet", ""))]
        listing_nums = re.findall(r"\$([\d,]+|n/a)", row.get("Listing Price", ""))
        lastsold_nums = re.findall(r"\$([\d,]+|n/a)", row.get("Last Sold", ""))
        statuses = row.get("Listing Status", "").split()

        n = len(sqft_nums) - 1  # exclude subject column
        for i in range(1, n + 1):
            sqft = sqft_nums[i] if i < len(sqft_nums) else None
            status = statuses[i] if i < len(statuses) else None
            lst = listing_nums[i] if i < len(listing_nums) else None
            sold = lastsold_nums[i] if i < len(lastsold_nums) else None
            lst_val = int(lst.replace(",", "")) if lst and lst != "n/a" else None
            sold_val = int(sold.replace(",", "")) if sold and sold != "n/a" else None
            price = lst_val if lst_val is not None else sold_val
            confirmed_closed = (lst_val is not None and sold_val is not None and lst_val != sold_val)
            if sqft and price:
                raw.append({"sqft": sqft, "price": price, "status": status,
                            "confirmed_closed": confirmed_closed})

    seen, unique = set(), []
    for c in raw:
        key = (c["sqft"], c["price"], c["status"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def compute_arv(comps, subject_sqft):
    """
    comps: list of {"sqft", "price", "status", "confirmed_closed"} from
    _parse_comp_table. Returns None if no usable comps or no subject sqft.
    """
    if not comps or not subject_sqft:
        return None
    ppsf = sorted(c["price"] / c["sqft"] for c in comps if c["sqft"])
    if not ppsf:
        return None
    n = len(ppsf)
    low, high = ppsf[0], ppsf[-1]
    median = ppsf[n // 2] if n % 2 == 1 else (ppsf[n // 2 - 1] + ppsf[n // 2]) / 2
    n_confirmed_closed = sum(1 for c in comps if c["confirmed_closed"])
    return {
        "comps_used": n,
        "confirmed_closed_sales": n_confirmed_closed,
        "basis": ("mixed listing/sold prices (few or no confirmed closed comps -- "
                  "treat as preliminary)" if n_confirmed_closed < max(3, n // 4)
                  else "predominantly confirmed closed sales"),
        "ppsf_low": round(low, 2),
        "ppsf_median": round(median, 2),
        "ppsf_high": round(high, 2),
        "arv_low": round(low * subject_sqft),
        "arv_median": round(median * subject_sqft),
        "arv_high": round(high * subject_sqft),
        "subject_sqft": subject_sqft,
    }


# --------------------------------------------------------------------------
# Parsing: Skip-trace lead export CSV
# --------------------------------------------------------------------------

def parse_lead_csv(path):
    """Extract key fields + contact/compliance data from the lead export CSV."""
    with open(path, encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))

    def money(v):
        if not v:
            return None
        return float(v.replace("$", "").replace(",", ""))

    def num(v):
        if v in (None, ""):
            return None
        try:
            return int(v)
        except ValueError:
            return float(v)

    data = {"source": "lead_csv", "file": str(path)}
    data["owner_name"] = f"{row.get('FirstName','').strip()} {row.get('LastName','').strip()}".strip()
    data["property_address"] = row.get("PropertyAddress", "").strip()
    data["property_full_address"] = ", ".join(filter(None, [
        row.get("PropertyAddress", "").strip(),
        row.get("PropertyCity", "").strip(),
        f"{row.get('PropertyState','').strip()} {row.get('PropertyPostalCode','').strip()}".strip(),
    ]))
    data["bedrooms"] = num(row.get("Beds"))
    data["bathrooms"] = num(row.get("Baths"))
    data["square_feet"] = num(row.get("SquareFootage"))
    data["lot_sqft"] = num(row.get("LotSizeSqFt"))
    data["year_built"] = num(row.get("YearBuilt"))
    data["last_sales_date"] = row.get("LastSalesDate")
    data["last_sales_price"] = money(row.get("LastSalesPrice"))
    data["avm"] = money(row.get("AVM"))
    data["market_value"] = money(row.get("MarketValue"))
    data["tax_assessed_value"] = money(row.get("TaxAssessedValue"))
    data["rental_estimate_low"] = money(row.get("RentalEstimateLow"))
    data["rental_estimate_high"] = money(row.get("RentalEstimateHigh"))
    data["wholesale_value"] = money(row.get("WholesaleValue"))
    data["number_of_loans"] = num(row.get("NumberOfLoans"))
    data["loan_amount"] = money(row.get("LoanAmount"))
    data["estimated_mortgage_balance"] = money(row.get("EstimatedMortgageBalance"))
    data["loan_recording_date"] = row.get("RecordingDate")
    data["loan_lender_name"] = row.get("LenderName")
    data["ltv_percent"] = row.get("LTV")
    data["free_and_clear"] = row.get("FreeAndClear") == "1"
    data["high_equity"] = row.get("HighEquity") == "1"

    # --- Live/recent MLS listing data embedded in the same export -------
    data["mls_current_status"] = row.get("MLS_Curr_Status") or None
    data["mls_current_list_price"] = money(row.get("MLS_Curr_ListPrice"))
    data["mls_current_beds"] = num(row.get("MLS_Curr_Beds"))
    data["mls_current_baths"] = num(row.get("MLS_Curr_Baths"))
    data["mls_prev_beds"] = num(row.get("MLS_Prev_Beds"))
    data["mls_prev_baths"] = num(row.get("MLS_Prev_Baths"))
    desc = row.get("MLS_Curr_Description", "") or row.get("MLS_Prev_Description", "") or ""
    data["mls_description_text"] = desc or None
    data["mls_current_list_date"] = row.get("MLS_Curr_ListDate") or None
    data["mls_prev_list_date"] = row.get("MLS_Prev_ListDate") or None
    data["mls_description_bedbath"] = None
    m = re.search(r"(\d+)[\s-]*[Bb]edroom.{0,20}?(\d+(?:\.\d+)?)[\s-]*[Bb]ath", desc)
    if m:
        data["mls_description_bedbath"] = {"beds": int(m.group(1)), "baths": float(m.group(2))}
    m2 = re.search(r"approximately\s+([\d,]+)\s+square feet of living area", desc, re.I)
    data["mls_living_area_sqft"] = int(m2.group(1).replace(",", "")) if m2 else None
    m3 = re.search(r"([\d,]+)\s+total square feet", desc, re.I)
    data["mls_total_area_sqft"] = int(m3.group(1).replace(",", "")) if m3 else None

    # --- Contact / compliance block -------------------------------------
    contacts = []
    for i in (1, 2, 3):
        phone = row.get(f"Contact1Phone_{i}")
        if phone:
            contacts.append({
                "phone": phone,
                "type": row.get(f"Contact1Phone_{i}_Type"),
                "dnc": row.get(f"Contact1Phone_{i}_DNC") == "True",
                "litigator": row.get(f"Contact1Phone_{i}_Litigator") == "True",
                "email": row.get(f"Contact1Email_{i}") or None,
            })
    data["contacts"] = contacts
    data["callable_numbers"] = [
        c["phone"] for c in contacts if not c["dnc"] and not c["litigator"]
    ]
    data["blocked_numbers"] = [
        {"phone": c["phone"], "reason": ("DNC" if c["dnc"] else "") +
         ("+Litigator" if c["litigator"] else "")}
        for c in contacts if c["dnc"] or c["litigator"]
    ]

    return data


# --------------------------------------------------------------------------
# Renovation detection
# --------------------------------------------------------------------------
# NEW LOGIC as of this build -- not recovered from a prior version. The prior
# session's renovation-detection code was never saved back to Drive as source
# (only its rendered output survived, and that output didn't include this
# section). Reimplemented from the description in project memory: four
# checks (loan activity, sale price changes, tax assessment changes, listing
# description keyword scan), plus a component-age/need assessment.

# Typical replacement lifespans (years) for components with a well-known
# service life. Kitchen/bath are intentionally excluded from hard estimates
# below -- their "need" is a cosmetic/style judgment, not a mechanical one.
COMPONENT_LIFESPANS = {
    "roof": 22,
    "hvac": 17,
    "water heater": 11,
    "furnace": 18,
    "windows": 25,
}

RENOVATION_KEYWORDS_POSITIVE = [
    "renovated", "remodeled", "updated", "new roof", "new hvac", "newer roof",
    "newer hvac", "gut renovation", "fully renovated", "recently updated",
    "move-in ready", "turnkey",
]
RENOVATION_KEYWORDS_NEGATIVE = [
    "fixer", "fixer-upper", "needs tlc", "as-is", "as is", "handyman special",
    "investor special", "cash only", "sold as-is", "needs work", "tear down",
    "estate sale", "motivated seller", "priced to sell",
]


def assess_component_need(year_built, as_of_year=None):
    """
    Given a property's year built, estimate which major mechanical components
    are likely due or overdue for replacement, purely from typical service
    life -- this is a baseline assumption used only when there's no direct
    renovation evidence (loan/listing signals) to go on. Kitchen/bath are
    reported separately as a cosmetic-dating note, not a hard "needs
    replacement" call, since their condition can't be inferred from age alone.
    """
    if not year_built:
        return {"error": "No year_built available -- cannot estimate component age."}
    as_of_year = as_of_year or datetime.now().year
    age = as_of_year - year_built
    if age < 0:
        return {"error": "year_built is in the future -- skipping component-age estimate."}

    components = {}
    for name, lifespan in COMPONENT_LIFESPANS.items():
        remaining = lifespan - age
        if remaining <= 0:
            status = "likely overdue for replacement"
        elif remaining <= 5:
            status = "approaching end of typical service life"
        else:
            status = "within typical service life"
        components[name] = {"typical_lifespan_years": lifespan, "property_age_years": age,
                             "estimated_remaining_years": remaining, "status": status}

    cosmetic_note = (
        f"Property is {age} years old. Kitchen/bath condition can't be inferred from age "
        f"alone -- if original to construction, styling is {age} years dated, but this is "
        f"a cosmetic judgment only, not a hard replacement estimate."
    )
    return {"age_years": age, "components": components, "cosmetic_note": cosmetic_note}


def scan_listing_language(description_text):
    """Check 4: keyword scan of the MLS listing description for renovation/
    condition signals in either direction (recently improved vs. needs work)."""
    if not description_text:
        return None
    text_lower = description_text.lower()
    positive_hits = [kw for kw in RENOVATION_KEYWORDS_POSITIVE if kw in text_lower]
    negative_hits = [kw for kw in RENOVATION_KEYWORDS_NEGATIVE if kw in text_lower]
    return {
        "recently_improved_keywords": positive_hits,
        "needs_work_keywords": negative_hits,
        "excerpt": description_text[:400],
    }


def detect_renovation_signals(sources, reconciled):
    """
    Runs the four renovation-detection checks against whatever sources are
    available, gracefully degrading to 'insufficient data' per check rather
    than skipping the section outright -- consistent with how the strategy
    scorer treats missing coverage (see recommend_strategies).
    """
    signals = {"checks": {}}

    # Check 1: loan activity -- a mortgage/HELOC recorded well after the
    # purchase date can indicate renovation financing.
    pp = sources.get("property_profile", {})
    mortgage = pp.get("mortgage")
    transfer_date = pp.get("transfer_date")
    if mortgage and transfer_date:
        signals["checks"]["loan_activity"] = {
            "signal": "possible_renovation_financing",
            "note": (f"A mortgage was recorded ({mortgage.get('recording_date')}) for "
                     f"${mortgage.get('loan_amount', 0):,.0f}. If this postdates the "
                     f"{transfer_date} purchase by more than a few months, it may reflect "
                     f"renovation/rehab financing rather than the original purchase loan -- "
                     f"compare dates directly before relying on this."),
        }
    else:
        signals["checks"]["loan_activity"] = {"signal": "insufficient_data",
            "note": "No property profile mortgage record and/or transfer date available."}

    # Check 2: sale price changes -- requires a multi-entry sales history,
    # which only comes from a manually-verified public_override.
    sales_history = reconciled.get("county_sales_history")
    if sales_history and len(sales_history) >= 2:
        try:
            prices = [s.get("price") for s in sales_history if s.get("price")]
            if len(prices) >= 2:
                pct_change = round(100 * (prices[-1] - prices[0]) / prices[0], 1) if prices[0] else None
                signals["checks"]["sale_price_changes"] = {
                    "signal": "price_trend_available",
                    "pct_change_first_to_last": pct_change,
                    "note": f"Sales history shows {len(prices)} recorded sales; overall change "
                            f"{pct_change}% -- a jump well above typical local appreciation between "
                            f"two close-together sale dates can indicate a renovation occurred in between.",
                }
            else:
                signals["checks"]["sale_price_changes"] = {"signal": "insufficient_data",
                    "note": "Sales history present but missing price figures."}
        except Exception:
            signals["checks"]["sale_price_changes"] = {"signal": "insufficient_data",
                "note": "Could not parse sales history for a price trend."}
    else:
        signals["checks"]["sale_price_changes"] = {"signal": "insufficient_data",
            "note": "No multi-entry sales history available (requires --public-override with sales_history)."}

    # Check 3: tax assessment changes -- requires a multi-year valuation
    # history, also only available via public_override.
    valuation_history = (sources.get("public_override") or {}).get("valuation_history")
    if valuation_history and len(valuation_history) >= 2:
        try:
            vals = [v.get("assessed_value") for v in valuation_history if v.get("assessed_value")]
            pct_change = round(100 * (vals[-1] - vals[0]) / vals[0], 1) if vals and vals[0] else None
            signals["checks"]["tax_assessment_changes"] = {
                "signal": "assessment_trend_available",
                "pct_change": pct_change,
                "note": f"Assessed value changed {pct_change}% across {len(vals)} years on file -- "
                        f"a jump outside the county's typical reappraisal pattern can indicate "
                        f"permitted improvements were added to the record.",
            }
        except Exception:
            signals["checks"]["tax_assessment_changes"] = {"signal": "insufficient_data",
                "note": "Could not parse valuation history."}
    else:
        signals["checks"]["tax_assessment_changes"] = {"signal": "insufficient_data",
            "note": "No multi-year valuation history available (requires --public-override with valuation_history)."}

    # Check 4: listing description keyword scan
    lc = sources.get("lead_csv", {})
    desc = lc.get("mls_description_text")
    lang = scan_listing_language(desc)
    if lang:
        signals["checks"]["listing_language"] = {
            "signal": "keywords_found" if (lang["recently_improved_keywords"] or lang["needs_work_keywords"]) else "no_keywords",
            **lang,
        }
    else:
        signals["checks"]["listing_language"] = {"signal": "insufficient_data",
            "note": "No MLS listing description text available in the CSV export."}
    signals["listing_language"] = signals["checks"]["listing_language"]

    # Component age/need baseline (only meaningful absent direct evidence above)
    year_built = reconciled.get("fields", {}).get("year_built", {}).get("value")
    signals["component_age_estimate"] = assess_component_need(year_built)

    return signals


# --------------------------------------------------------------------------
# Strategy scoring
# --------------------------------------------------------------------------
# NEW LOGIC as of this build -- same caveat as renovation detection above:
# reimplemented from the memory description (9 strategies, qualitative
# rating, decision-support framing), not recovered from prior source code.
# Thresholds below are reasonable starting heuristics, not validated against
# a known-good output -- treat them as a first draft to tune against real
# deals, the same way the rest of this pipeline was built and refined.

STRATEGIES = [
    "Wholesale", "Fix & Flip", "BRRRR", "Buy & Hold", "Short-Term Rental",
    "Subject-To", "Seller Financing", "MLS Sale", "Turnkey Rental",
]

RATING_ORDER = {"Strong fit": 0, "Possible fit": 1, "Weak fit": 2, "Insufficient data": 3}


def recommend_strategies(reconciled, sources):
    """
    Scores each of the 9 strategies as decision support, not a
    recommendation. 'Insufficient data' reflects gaps in what was reconciled
    for this property, not a judgment on deal quality -- it means the
    signals this strategy depends on weren't available this run.
    """
    arv = reconciled.get("arv_analysis")
    lc = sources.get("lead_csv", {})
    renov = reconciled.get("renovation_signals", {})
    listing_lang = renov.get("listing_language", {})
    positive_kw = listing_lang.get("recently_improved_keywords", [])
    needs_work_kw = listing_lang.get("needs_work_keywords", [])

    last_sale = reconciled.get("fields", {}).get("last_sale_price", {}).get("value")
    avm = (reconciled.get("valuation_bases", {}) or {}).get("comps_avm") or \
          (reconciled.get("valuation_bases", {}) or {}).get("csv_avm")
    basis_price = last_sale or avm

    arv_spread_pct = None
    if arv and basis_price:
        arv_spread_pct = round(100 * (arv["arv_median"] - basis_price) / basis_price, 1)

    rental_low = lc.get("rental_estimate_low")
    rental_high = lc.get("rental_estimate_high")
    has_rental_data = bool(rental_low or rental_high)

    free_and_clear = lc.get("free_and_clear")
    high_equity = lc.get("high_equity")
    mortgage_flags = [f["flag"] for f in reconciled.get("flags", [])]
    loan_status_uncertain = any(f in mortgage_flags for f in (
        "NAME_MISMATCH_REVIEW_REQUIRED", "CURRENT_MORTGAGE_RECORD_IS_STALE",
        "LOAN_RELEASED_BUT_SOURCE_SHOWS_ACTIVE_BALANCE", "MORTGAGE_VS_FREE_AND_CLEAR_CONFLICT",
    ))
    has_mortgage = bool(reconciled.get("mortgage_record"))

    fixer_signal = bool(needs_work_kw)
    turnkey_signal = bool(positive_kw) and not fixer_signal
    features_text = (sources.get("comps_report", {}).get("subject_address") or "")

    results = []

    def add(strategy, rating, supporting, complicating):
        results.append({"strategy": strategy, "rating": rating,
                         "supporting_factors": supporting, "complicating_factors": complicating})

    # --- Wholesale ---
    sup, comp = [], []
    if fixer_signal: sup.append("Listing language suggests fixer/investor-facing condition.")
    if arv_spread_pct is not None:
        (sup if arv_spread_pct >= 20 else comp).append(f"ARV spread vs. basis price is {arv_spread_pct}%.")
    if not fixer_signal and not arv: comp.append("No fixer signal and no ARV data to judge spread.")
    if arv is None and not fixer_signal:
        add("Wholesale", "Insufficient data", sup, comp + ["Missing both ARV and listing-language signals."])
    elif fixer_signal and arv_spread_pct is not None and arv_spread_pct >= 20:
        add("Wholesale", "Strong fit", sup, comp)
    elif fixer_signal or (arv_spread_pct is not None and arv_spread_pct >= 15):
        add("Wholesale", "Possible fit", sup, comp)
    else:
        add("Wholesale", "Weak fit", sup, comp)

    # --- Fix & Flip ---
    sup, comp = [], []
    if fixer_signal: sup.append("Listing language indicates the property needs work.")
    if arv_spread_pct is not None:
        (sup if arv_spread_pct >= 15 else comp).append(f"ARV spread vs. basis price is {arv_spread_pct}% (needs to cover rehab + profit).")
    if arv is None:
        add("Fix & Flip", "Insufficient data", sup, comp + ["No ARV analysis available to size the spread."])
    elif fixer_signal and arv_spread_pct is not None and arv_spread_pct >= 15:
        add("Fix & Flip", "Strong fit", sup, comp)
    elif fixer_signal or (arv_spread_pct is not None and arv_spread_pct >= 10):
        add("Fix & Flip", "Possible fit", sup, comp)
    else:
        comp.append("No renovation signal and/or thin ARV spread.")
        add("Fix & Flip", "Weak fit", sup, comp)

    # --- BRRRR ---
    sup, comp = [], []
    if has_rental_data: sup.append(f"Rental estimate on file (${rental_low or 0:,.0f}-${rental_high or 0:,.0f}).")
    if arv_spread_pct is not None and arv_spread_pct >= 15: sup.append(f"ARV spread of {arv_spread_pct}% supports post-rehab refinance room.")
    if not has_rental_data or arv is None:
        add("BRRRR", "Insufficient data", sup, comp + ["Needs both rental estimate and ARV data to evaluate refinance math."])
    elif has_rental_data and arv_spread_pct is not None and arv_spread_pct >= 15:
        add("BRRRR", "Strong fit", sup, comp)
    elif has_rental_data or (arv_spread_pct is not None and arv_spread_pct >= 10):
        add("BRRRR", "Possible fit", sup, comp)
    else:
        add("BRRRR", "Weak fit", sup, comp)

    # --- Buy & Hold ---
    sup, comp = [], []
    if has_rental_data: sup.append("Rental estimate on file supports a cash-flow read.")
    if turnkey_signal: sup.append("Listing language suggests move-in-ready condition (less renovation risk for a hold).")
    if fixer_signal: comp.append("Needs work before it can be rent-ready.")
    if not has_rental_data:
        add("Buy & Hold", "Insufficient data", sup, comp + ["No rental estimate available."])
    elif has_rental_data and not fixer_signal:
        add("Buy & Hold", "Strong fit" if turnkey_signal else "Possible fit", sup, comp)
    else:
        add("Buy & Hold", "Possible fit" if has_rental_data else "Weak fit", sup, comp)

    # --- Short-Term Rental ---
    sup, comp = [], []
    stray_features = [w for w in ("waterfront", "pool", "lake", "beach", "resort")
                       if w in (features_text or "").lower() or w in (positive_kw and " ".join(positive_kw).lower() or "")]
    if stray_features: sup.append(f"Location/feature signals present: {', '.join(stray_features)}.")
    if has_rental_data: sup.append("Rental estimate on file (long-term basis; STR would need separate comp research).")
    if not stray_features:
        add("Short-Term Rental", "Insufficient data", sup,
            comp + ["No location/amenity signal detected in available text; STR viability needs dedicated market research (occupancy, local regulation) not covered by this pipeline."])
    else:
        add("Short-Term Rental", "Possible fit", sup, comp + ["STR-specific occupancy/regulatory research still needed."])

    # --- Subject-To ---
    sup, comp = [], []
    if has_mortgage and not loan_status_uncertain: sup.append("An existing mortgage record is on file and not currently flagged as uncertain.")
    if loan_status_uncertain: comp.append("Loan status has open verification flags (see Data Verification) -- terms cannot be confirmed as clean.")
    if free_and_clear: comp.append("Source data marks the property free and clear -- no loan to take subject-to.")
    if not has_mortgage:
        add("Subject-To", "Insufficient data", sup, comp + ["No mortgage record found to evaluate."])
    elif free_and_clear:
        add("Subject-To", "Weak fit", sup, comp)
    elif has_mortgage and not loan_status_uncertain:
        add("Subject-To", "Possible fit", sup, comp)
    else:
        add("Subject-To", "Weak fit", sup, comp)

    # --- Seller Financing ---
    sup, comp = [], []
    if free_and_clear or high_equity: sup.append("Source data suggests meaningful equity/free-and-clear position -- seller has room to finance.")
    if needs_work_kw: sup.append("Listing language ('" + "', '".join(needs_work_kw[:2]) + "') may indicate a motivated seller.")
    if not (free_and_clear or high_equity):
        add("Seller Financing", "Insufficient data", sup, comp + ["No equity/free-and-clear signal available to judge seller's financing capacity."])
    elif (free_and_clear or high_equity) and needs_work_kw:
        add("Seller Financing", "Strong fit", sup, comp)
    else:
        add("Seller Financing", "Possible fit", sup, comp)

    # --- MLS Sale (traditional retail listing) ---
    sup, comp = [], []
    if turnkey_signal: sup.append("Listing language suggests retail-ready condition.")
    if fixer_signal: comp.append("Needs work first -- retail buyers typically want move-in-ready.")
    if not positive_kw and not needs_work_kw:
        add("MLS Sale", "Insufficient data", sup, comp + ["No listing-language signal either way."])
    elif turnkey_signal:
        add("MLS Sale", "Strong fit", sup, comp)
    elif fixer_signal:
        add("MLS Sale", "Weak fit", sup, comp)
    else:
        add("MLS Sale", "Possible fit", sup, comp)

    # --- Turnkey Rental ---
    sup, comp = [], []
    if turnkey_signal and has_rental_data: sup.append("Move-in-ready condition plus an on-file rental estimate.")
    if fixer_signal: comp.append("Needs work before it's rent-ready as a turnkey unit.")
    if not has_rental_data:
        add("Turnkey Rental", "Insufficient data", sup, comp + ["No rental estimate available."])
    elif turnkey_signal and has_rental_data:
        add("Turnkey Rental", "Strong fit", sup, comp)
    elif has_rental_data and not fixer_signal:
        add("Turnkey Rental", "Possible fit", sup, comp)
    else:
        add("Turnkey Rental", "Weak fit", sup, comp)

    results.sort(key=lambda r: RATING_ORDER.get(r["rating"], 9))
    return results


# --------------------------------------------------------------------------
# Reconciliation
# --------------------------------------------------------------------------

FIELD_TRUST_ORDER = ["public_override", "mls_listing", "comps_report", "lead_csv", "property_profile"]

def money(n):
    if n is None:
        return "N/A"
    return f"${n:,.0f}"

# Which sources are treated as corroborating each other (tier 2 of hierarchy)
COMPS_TIER = {"comps_report", "lead_csv"}


def name_similarity_flag(owner_name, mortgage_borrowers):
    """Very deliberately simple/conservative name check: flags for human review
    rather than trying to auto-resolve. Never silently accepts a mismatch."""
    if not owner_name or not mortgage_borrowers:
        return None
    owner_tokens = set(re.findall(r"[A-Za-z]+", owner_name.upper()))
    borrower_tokens = set(re.findall(r"[A-Za-z]+", mortgage_borrowers.upper()))
    overlap = owner_tokens & borrower_tokens
    # Suffixes / extra names on the borrower side not present on the owner side
    extra_on_borrower = borrower_tokens - owner_tokens
    suspicious_suffixes = {"JR", "SR", "II", "III", "IV"} & extra_on_borrower
    if suspicious_suffixes or len(overlap) < max(1, len(owner_tokens) - 1):
        return {
            "flag": "NAME_MISMATCH_REVIEW_REQUIRED",
            "owner_name": owner_name,
            "mortgage_borrowers": mortgage_borrowers,
            "note": (
                "Borrower name on the mortgage record does not cleanly match the "
                "property owner name. This has previously turned out to be a "
                "misattributed record (a different person, e.g. a family member "
                "with a similar name). Do not use this loan figure in a client "
                "deliverable until verified against the county Clerk of Court."
            ),
        }
    return None


def reconcile(sources, public_override=None):
    """sources: dict of {source_name: parsed_dict}. Returns reconciled record."""
    reconciled = {"fields": {}, "conflicts": [], "compliance": {}, "flags": []}

    compare_fields = [
        ("bedrooms", int),
        ("bathrooms", float),
        ("square_feet", int),
        ("year_built", int),
        ("lot_sqft", int),
    ]

    # Map source dicts to a uniform lookup, keyed by our trust hierarchy names
    by_name = {}
    if "property_profile" in sources:
        by_name["property_profile"] = sources["property_profile"]
    if "comps_report" in sources:
        by_name["comps_report"] = sources["comps_report"]
    if "lead_csv" in sources:
        by_name["lead_csv"] = sources["lead_csv"]
    if public_override:
        by_name["public_override"] = public_override

    # MLS-embedded listing data (from a licensed agent's actual listing) is
    # more reliable for bed/bath than aggregator top-line fields when present.
    if "lead_csv" in sources:
        lc = sources["lead_csv"]
        mls_beds = lc.get("mls_current_beds") or lc.get("mls_prev_beds")
        mls_baths = lc.get("mls_current_baths") or lc.get("mls_prev_baths")
        if mls_beds or mls_baths:
            by_name["mls_listing"] = {"bedrooms": mls_beds, "bathrooms": mls_baths}

    for field, _cast in compare_fields:
        values = {}
        for src_name, src_data in by_name.items():
            v = src_data.get(field)
            if v is not None:
                values[src_name] = v

        if not values:
            continue

        distinct_vals = set(values.values())
        if len(distinct_vals) == 1:
            reconciled["fields"][field] = {
                "value": distinct_vals.pop(),
                "confidence": "agreed",
                "sources": list(values.keys()),
            }
            continue

        # Conflict — resolve via trust hierarchy
        chosen_source = None
        for tier in FIELD_TRUST_ORDER:
            if tier in values:
                chosen_source = tier
                break

        # If the two "corroborating" tier sources agree with each other,
        # that's stronger evidence than a single higher-tier source alone
        # (except public_override, which always wins outright).
        if "public_override" not in values and "mls_listing" not in values:
            tier2_vals = {s: v for s, v in values.items() if s in COMPS_TIER}
            if len(tier2_vals) >= 2 and len(set(tier2_vals.values())) == 1:
                chosen_source = next(iter(tier2_vals))

        reconciled["fields"][field] = {
            "value": values[chosen_source],
            "confidence": "resolved_by_trust_hierarchy",
            "chosen_source": chosen_source,
            "all_values": values,
        }
        reconciled["conflicts"].append({
            "field": field,
            "all_values": values,
            "resolved_to": values[chosen_source],
            "resolved_from": chosen_source,
        })

    # --- Sale price / date (compare across sources) ----------------------
    sale_values = {}
    if "property_profile" in by_name and by_name["property_profile"].get("transfer_value"):
        sale_values["property_profile"] = by_name["property_profile"]["transfer_value"]
    if "comps_report" in by_name and by_name["comps_report"].get("last_sold_price"):
        sale_values["comps_report"] = by_name["comps_report"]["last_sold_price"]
    if "lead_csv" in by_name and by_name["lead_csv"].get("last_sales_price"):
        sale_values["lead_csv"] = by_name["lead_csv"]["last_sales_price"]
    if "public_override" in by_name and by_name["public_override"].get("last_sale_price"):
        sale_values["public_override"] = by_name["public_override"]["last_sale_price"]
    if sale_values:
        distinct = set(sale_values.values())
        if len(distinct) == 1:
            reconciled["fields"]["last_sale_price"] = {
                "value": distinct.pop(), "confidence": "agreed", "sources": list(sale_values.keys())
            }
        else:
            tier2 = {s: v for s, v in sale_values.items() if s in COMPS_TIER}
            chosen = next(iter(tier2.values())) if tier2 else next(iter(sale_values.values()))
            reconciled["fields"]["last_sale_price"] = {
                "value": chosen, "confidence": "resolved_by_trust_hierarchy", "all_values": sale_values
            }
            reconciled["conflicts"].append({
                "field": "last_sale_price", "all_values": sale_values, "resolved_to": chosen
            })

    # --- Valuation figures (not necessarily conflicting -- different methodologies,
    #     but worth surfacing together so nobody accidentally mixes bases) --------
    valuations = {}
    if "property_profile" in by_name:
        valuations["property_profile_assessed"] = by_name["property_profile"].get("assessed_value")
        valuations["property_profile_market_reported"] = by_name["property_profile"].get("market_value_reported")
    if "comps_report" in by_name:
        valuations["comps_avm"] = by_name["comps_report"].get("avm")
        valuations["comps_estimated_value"] = by_name["comps_report"].get("estimated_value")
    if "lead_csv" in by_name:
        valuations["csv_avm"] = by_name["lead_csv"].get("avm")
        valuations["csv_market_value"] = by_name["lead_csv"].get("market_value")
        valuations["csv_tax_assessed"] = by_name["lead_csv"].get("tax_assessed_value")
    if "public_override" in by_name:
        po = by_name["public_override"]
        for k in ("land_value", "building_value", "total_value", "assessed_value"):
            if po.get(k) is not None:
                valuations[f"county_official_{k}"] = po[k]

    reconciled["valuation_bases"] = valuations

    # --- ARV analysis from comps list (if available) ----------------------
    if "comps_report" in by_name and by_name["comps_report"].get("comps"):
        subj_sqft = reconciled["fields"].get("square_feet", {}).get("value")
        arv = compute_arv(by_name["comps_report"]["comps"], subj_sqft)
        if arv:
            reconciled["arv_analysis"] = arv
            if arv["confirmed_closed_sales"] < max(3, arv["comps_used"] // 4):
                reconciled["flags"].append({
                    "flag": "ARV_BASIS_MOSTLY_LISTING_PRICE",
                    "note": (
                        f"ARV estimate ({money(arv['arv_low'])} - {money(arv['arv_median'])} - "
                        f"{money(arv['arv_high'])}) computed from {arv['comps_used']} deduplicated "
                        f"comps using mixed listing/sold prices (few or no confirmed closed comps -- "
                        f"treat as preliminary). Note: only {arv['confirmed_closed_sales']} of these "
                        f"have a confirmed closed sale price (differs from listing price); the rest use "
                        f"asking/listing price as a proxy. Treat this as a preliminary range, not a "
                        f"final ARV -- verify against actual closed comps (MLS or county records) "
                        f"before using in a client deliverable."
                    ),
                })

    # --- Building area vs. "square_feet": county assessor building-area figures
    # often measure TOTAL structure (which can include unheated space, additions,
    # garages) while MLS/AVM "square feet" typically means heated living area.
    # These are legitimately different measurements, not necessarily a data error --
    # so we surface both rather than silently picking one. -----------------------
    if "public_override" in by_name and by_name["public_override"].get("building_area_sqft"):
        county_building_area = by_name["public_override"]["building_area_sqft"]
        reconciled["county_building_area_sqft"] = county_building_area
        resolved_sqft = reconciled["fields"].get("square_feet", {}).get("value")
        if resolved_sqft and abs(county_building_area - resolved_sqft) > 0.1 * resolved_sqft:
            reconciled["flags"].append({
                "flag": "BUILDING_AREA_VS_LIVING_AREA_DIVERGENCE",
                "note": (
                    f"County assessor lists total building area as {county_building_area} sqft, "
                    f"but the resolved living-area figure from MLS/AVM sources is {resolved_sqft} sqft. "
                    f"This gap ({county_building_area - resolved_sqft} sqft) may reflect unheated space, "
                    f"a garage, additions, or an outdated assessor record rather than an error -- "
                    f"confirm via a field measurement or appraisal before using either figure in a "
                    f"rehab budget or ARV calculation."
                ),
            })

    # --- Sales history corroboration (informational, not conflict-resolved) -----
    if "public_override" in by_name and by_name["public_override"].get("sales_history"):
        reconciled["county_sales_history"] = by_name["public_override"]["sales_history"]
    if (valuations.get("property_profile_assessed") and valuations.get("csv_tax_assessed")
            and valuations["property_profile_assessed"] != valuations["csv_tax_assessed"]):
        # not necessarily an error -- just flag for eyes
        pass

    # --- Mortgage / lien anomaly check -----------------------------------
    owner_name = None
    if "lead_csv" in by_name:
        owner_name = by_name["lead_csv"].get("owner_name")
    elif "property_profile" in by_name:
        owner_name = by_name["property_profile"].get("owner_name")

    mortgage = by_name.get("property_profile", {}).get("mortgage")
    reconciled["mortgage_record"] = mortgage
    csv_says_free_and_clear = by_name.get("lead_csv", {}).get("free_and_clear")

    if mortgage:
        # Skip the generic mismatch flag when the borrower cleanly matches the
        # PRIOR owner/seller -- that's an expected historical record (e.g. a
        # loan the previous owner took out before selling), not a data error.
        pp_for_check = by_name.get("property_profile", {})
        seller_for_check = (pp_for_check.get("purchase_seller") or "").upper()
        borrower_for_check = (mortgage.get("borrower_names") or "").upper()
        seller_tok = set(re.findall(r"[A-Za-z]+", seller_for_check))
        borrower_tok = set(re.findall(r"[A-Za-z]+", borrower_for_check))
        is_explained_by_prior_owner = bool(seller_tok) and bool(borrower_tok) and \
            len(borrower_tok & seller_tok) >= max(1, len(borrower_tok) - 1)

        if not is_explained_by_prior_owner:
            name_flag = name_similarity_flag(owner_name, mortgage.get("borrower_names"))
            if name_flag:
                reconciled["flags"].append(name_flag)
        if csv_says_free_and_clear:
            reconciled["flags"].append({
                "flag": "MORTGAGE_VS_FREE_AND_CLEAR_CONFLICT",
                "note": (
                    f"Property Profile shows an active mortgage (${mortgage['loan_amount']:,.0f} "
                    f"from {mortgage['lender_name']}) but the CSV/skip-trace source marks this "
                    f"property FreeAndClear=True with $0 loan balance. Do not report a debt "
                    f"payoff or equity-arbitrage figure until this is resolved against the "
                    f"county Clerk of Court conveyance/mortgage records."
                ),
            })

    # --- "CURRENT MORTGAGE RECORD" mislabeling check ----------------------
    # Seen in practice: this report format can label a PRIOR owner's old,
    # already-superseded loan as the "current" mortgage. Detect by checking
    # whether the current-mortgage-record borrower matches the purchase-
    # section SELLER (prior owner) rather than the actual current owner.
    pp = by_name.get("property_profile", {})
    cur_mort = pp.get("current_mortgage_record")
    if cur_mort and owner_name:
        seller = pp.get("purchase_seller") or ""
        borrower = cur_mort.get("borrower_names", "")
        owner_tokens = set(re.findall(r"[A-Za-z]+", owner_name.upper()))
        borrower_tokens = set(re.findall(r"[A-Za-z]+", borrower.upper()))
        seller_tokens = set(re.findall(r"[A-Za-z]+", seller.upper()))
        if borrower_tokens and seller_tokens and borrower_tokens & seller_tokens and not (borrower_tokens & owner_tokens):
            reconciled["flags"].append({
                "flag": "CURRENT_MORTGAGE_RECORD_IS_STALE",
                "note": (
                    f"The Property Profile's 'CURRENT MORTGAGE RECORD' section shows a loan "
                    f"(${cur_mort['loan_amount']:,.0f}, recorded {cur_mort['recording_date']}) "
                    f"under borrower '{borrower}', who matches the PRIOR owner/seller "
                    f"('{seller}'), not the current owner ('{owner_name}'). This report format "
                    f"has a known pattern of mislabeling an old, superseded loan as 'current.' "
                    f"Do not present this as the property's active debt without verification."
                ),
            })

    # --- Recorded release vs. CSV still showing an active loan ------------
    if pp.get("mortgage_release") and "lead_csv" in by_name:
        csv_data = by_name["lead_csv"]
        release = pp["mortgage_release"]
        if csv_data.get("number_of_loans", 0) and csv_data.get("estimated_mortgage_balance"):
            same_lender = (pp.get("purchase_lender") or "").upper().split()[:1] == \
                          (csv_data.get("loan_lender_name") or "").upper().split()[:1]
            reconciled["flags"].append({
                "flag": "LOAN_RELEASED_BUT_SOURCE_SHOWS_ACTIVE_BALANCE",
                "note": (
                    f"Property Profile shows the purchase-money mortgage "
                    f"(${pp.get('purchase_first_td', 0):,.0f} from {pp.get('purchase_lender', 'unknown lender')}) "
                    f"was RELEASED on {release['date']} (doc {release['doc']}). But the skip-trace/CSV "
                    f"source still shows {csv_data['number_of_loans']} active loan(s) with an estimated "
                    f"balance of ${csv_data['estimated_mortgage_balance']:,.0f} "
                    f"({'same lender' if same_lender else 'lender name differs'}). The CSV's mortgage-balance "
                    f"estimate is very likely stale (probably just amortizing the original loan forward "
                    f"without accounting for the release). Do not use the CSV equity/LTV figures for this "
                    f"property until verified against the Clerk of Court release record cited above."
                ),
            })

    # --- MLS-embedded bed/bath vs. resolved top-line figures ---------------
    if "lead_csv" in by_name:
        csv_data = by_name["lead_csv"]
        mls_beds = csv_data.get("mls_current_beds") or csv_data.get("mls_prev_beds")
        mls_baths = csv_data.get("mls_current_baths") or csv_data.get("mls_prev_baths")
        resolved_beds = reconciled["fields"].get("bedrooms", {}).get("value")
        resolved_baths = reconciled["fields"].get("bathrooms", {}).get("value")
        raw_topline_beds = csv_data.get("bedrooms")
        if mls_beds and raw_topline_beds and mls_beds != raw_topline_beds:
            reconciled["flags"].append({
                "flag": "MLS_LISTING_BEDBATH_USED_OVER_TOPLINE",
                "note": (
                    f"The skip-trace/comps top-line fields report {raw_topline_beds}bd/"
                    f"{csv_data.get('bathrooms')}ba, but the actual MLS listing data embedded in the "
                    f"same export shows {mls_beds}bd/{mls_baths}ba (confirmed by both the current and "
                    f"prior MLS listings and the agent's own description text). The resolved figure "
                    f"above uses the MLS value as more reliable -- flagging so this override is visible "
                    f"rather than silent."
                ),
            })

    # --- Live MLS status (materially changes the deal context) ------------
    if "lead_csv" in by_name:
        csv_data = by_name["lead_csv"]
        if csv_data.get("mls_current_status"):
            reconciled["mls_current_listing_status"] = {
                "status": csv_data["mls_current_status"],
                "list_price": csv_data.get("mls_current_list_price"),
            }
            if csv_data["mls_current_status"].lower() in ("pending", "active", "active under contract"):
                reconciled["flags"].append({
                    "flag": "PROPERTY_CURRENTLY_ON_MLS",
                    "note": (
                        f"This property shows an MLS status of '{csv_data['mls_current_status']}' "
                        f"with a list price of {money(csv_data.get('mls_current_list_price'))}. "
                        f"This is not a cold off-market lead -- confirm whether this matches your "
                        f"own contract on the property before treating any 'opportunity spread' "
                        f"figures as real."
                    ),
                })

    # --- Compliance screen -------------------------------------------------
    if "lead_csv" in by_name:
        csv_data = by_name["lead_csv"]
        reconciled["compliance"] = {
            "callable_numbers": csv_data.get("callable_numbers", []),
            "blocked_numbers": csv_data.get("blocked_numbers", []),
        }
        if csv_data.get("blocked_numbers"):
            reconciled["flags"].append({
                "flag": "DNC_OR_LITIGATOR_NUMBERS_PRESENT",
                "note": (
                    "One or more contact numbers for this lead are flagged DNC and/or "
                    "litigator. These must be excluded from any outbound call list. "
                    "Only 'callable_numbers' should be loaded into the dialer/CRM."
                ),
                "blocked": csv_data.get("blocked_numbers"),
            })

    # --- Renovation signals + strategy recommendations (run last -- both
    # depend on fields/flags/arv_analysis computed above) -------------------
    reconciled["renovation_signals"] = detect_renovation_signals(sources, reconciled)
    reconciled["strategy_recommendations"] = recommend_strategies(reconciled, sources)

    return reconciled


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Reconcile property data sources.")
    ap.add_argument("--profile", type=Path, help="Property Profile Report PDF")
    ap.add_argument("--comps", type=Path, help="Comps Report PDF (Dealio.pro)")
    ap.add_argument("--csv", type=Path, help="Skip-trace lead export CSV")
    ap.add_argument("--public-override", type=Path,
                     help="JSON file with manually-verified public record fields "
                          "(highest trust tier). See public_override.example.json")
    ap.add_argument("--address", type=str,
                     help="Full property address for the Demographics & Economics section "
                          "(Census geocode + ACS + PEP + BLS). If omitted, the tool falls back "
                          "to the address embedded in the CSV/profile sources, if any.")
    ap.add_argument("--no-demographics", action="store_true",
                     help="Skip the Demographics & Economics section even if an address is available.")
    ap.add_argument("--ai-insight", type=Path,
                     help="Text file containing the copy-pasted 'Dealio Pro Ai Investment Insight' "
                          "(buy/hold verdict + bullet points) from the property's Overview tab. "
                          "Shown in the brief as a clearly-labeled third-party AI opinion, separate "
                          "from the reconciled/verified figures.")
    ap.add_argument("--out", type=Path, required=True, help="Output JSON path")
    args = ap.parse_args()

    sources = {}
    if args.profile:
        sources["property_profile"] = parse_property_profile(args.profile)
    if args.comps:
        sources["comps_report"] = parse_comps_report(args.comps)
    if args.csv:
        sources["lead_csv"] = parse_lead_csv(args.csv)

    public_override = None
    if args.public_override and args.public_override.exists():
        with open(args.public_override) as f:
            public_override = json.load(f)

    if not sources:
        print("No source files provided.", file=sys.stderr)
        sys.exit(1)

    reconciled = reconcile(sources, public_override)

    # Resolve the address to geocode: explicit --address wins, otherwise fall back
    # to the same source precedence generate_brief.js uses for its cover-page address.
    resolved_address = args.address
    if not resolved_address:
        resolved_address = (
            sources.get("lead_csv", {}).get("property_full_address")
            or sources.get("property_profile", {}).get("site_address")
        )

    demographics = None
    if not args.no_demographics and resolved_address:
        if fetch_demographics is None:
            demographics = {"error": "fetch_demographics.py not found alongside reconcile.py"}
        else:
            demographics = fetch_demographics(resolved_address)
    elif not args.no_demographics:
        demographics = {"error": "No property address available (pass --address explicitly)"}

    if demographics is not None:
        reconciled["demographics_economics"] = demographics

    if args.ai_insight and args.ai_insight.exists():
        insight_text = args.ai_insight.read_text().strip()
        if insight_text:
            reconciled["dealio_ai_insight"] = {
                "text": insight_text,
                "source": "Dealio Pro Ai -- Investment Insight (property Overview tab)",
                "disclaimer": ("Automated, informational-only AI output from a third-party platform. "
                                "This is a tool-generated opinion, not a reconciled/verified figure -- "
                                "treat it as one more input alongside the rest of this brief, not as "
                                "confirmed fact."),
            }

    output = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "raw_sources": sources,
        "reconciled": reconciled,
    }

    args.out.write_text(json.dumps(output, indent=2, default=str))
    print(f"Reconciled data written to {args.out}")

    # Human-readable summary to stdout
    print("\n=== CONFLICTS ===")
    for c in reconciled["conflicts"]:
        print(f"  {c['field']}: {c['all_values']}  -->  resolved to {c.get('resolved_to')}")
    print("\n=== FLAGS ===")
    for fl in reconciled["flags"]:
        print(f"  [{fl['flag']}] {fl.get('note', '')}")


if __name__ == "__main__":
    main()
