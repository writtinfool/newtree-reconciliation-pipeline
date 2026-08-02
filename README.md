# Newtree Capital -- Property Data Reconciliation Pipeline

Reconciles property data from multiple sources (SendFuse Property Profile PDF,
Dealio.pro Comps Report PDF, Dealio.pro/LeadPipes skip-trace CSV, optional
manually-verified public-record override) into a single trusted record, then
generates a client-ready "Investment Underwriting Brief" Word document.

## Files

- `reconcile.py` -- parses all sources, resolves conflicts via a trust
  hierarchy, computes ARV from comps, detects renovation signals, scores
  9 exit strategies, pulls Census/BLS demographics, and writes a single
  reconciled JSON.
- `generate_brief.js` -- reads that JSON and produces the branded docx brief.
- `fetch_demographics.py` -- standalone Census geocoder / ACS / PEP / BLS
  module, imported by reconcile.py. Needs a free Census API key
  (https://api.census.gov/data/key_signup.html) set as the CENSUS_API_KEY
  environment variable for population/income/renter-% figures; unemployment
  and geocoding work without a key.

## Usage

```bash
export CENSUS_API_KEY="your_key_here"   # optional but recommended

python3 reconcile.py \
  --profile "PropertyProfile.pdf" \
  --comps "CompsReport.pdf" \
  --csv "lpp-export-....csv" \
  --public-override public_override.json \
  --address "123 Main St, City, ST" \
  --ai-insight dealio_ai_note.txt \
  --out reconciled.json

node generate_brief.js reconciled.json brief.docx "Newtree Capital Resources LLC"
```

Any of `--profile` / `--comps` / `--csv` / `--public-override` / `--address` /
`--ai-insight` may be omitted -- the tool reconciles with whatever it's given
and notes what's missing rather than failing.

## Brief sections (in order)

Executive Summary -> Comps & ARV Analysis -> Renovation History Signals ->
Listing Language -> Strategy Recommendations -> Observations -> Demographics
& Economics -> Third-Party AI Insight (Dealio) -> Data Verification (open
items) -> Limitations & Disclaimer.

## Setup

```bash
npm install docx
pip install pdfplumber --break-system-packages
```

See CHANGELOG.md for what's built, what's new/unvalidated, and what's planned.
