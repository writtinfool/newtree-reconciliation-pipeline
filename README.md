# Newtree Capital -- Property Data Reconciliation Pipeline

Reconciles property data from multiple sources (SendFuse Property Profile PDF,
Dealio.pro Comps Report PDF, Dealio.pro/LeadPipes skip-trace CSV, optional
manually-verified public-record override) into a single trusted record, then
generates client-ready Word documents from three perspectives: an investment
underwriting brief, a neutral property fact sheet, and a loan collateral
summary.

## Files

- `reconcile.py` -- parses all sources, resolves conflicts via a trust
  hierarchy, computes ARV from comps, computes equity/LTV collateral analysis,
  detects renovation signals and distress/motivation flags, scores 9 exit
  strategies, pulls Census/BLS demographics, and writes a single reconciled
  JSON. Every report generator below reads this same JSON -- run it once per
  property, generate as many of the three views as you need from it.
- `generate_brief.js` -- **Investment Underwriting Brief.** Verified figures,
  ARV, renovation signals, strategy recommendations, demographics, open
  verification items. The "should I do this deal" document.
- `fact_sheet/build_fact_sheet.js` -- **Property Fact Sheet.** Neutral,
  comprehensive rundown of everything on file (structure, valuation, tax,
  financing, MLS history, all recorded status flags) with no strategy
  recommendation or interpretation. The "here's everything we know" document.
- `collateral_summary/build_collateral_summary.js` -- **Loan Collateral
  Summary.** Lender-perspective risk assessment: existing lien position, LTV
  against every valuation basis on hand, a risk rating, and an underwriting
  recommendation. Only produced when `reconcile.py` had enough data (a loan
  balance + at least one valuation) to compute `collateral_analysis` --
  otherwise the script explains why and exits rather than guessing.
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
node fact_sheet/build_fact_sheet.js reconciled.json fact_sheet.docx "Newtree Capital Resources LLC"
node collateral_summary/build_collateral_summary.js reconciled.json collateral_summary.docx "Newtree Capital Resources LLC"
```

Any of `--profile` / `--comps` / `--csv` / `--public-override` / `--address` /
`--ai-insight` may be omitted -- the tool reconciles with whatever it's given
and notes what's missing rather than failing.

### Contact info policy (opt-in, off by default)

None of the three generators print owner contact info (name, phone, email,
DNC/litigator flags) unless you pass `--include-contact-info`:

```bash
node generate_brief.js reconciled.json brief.docx "Company" --include-contact-info
```

This is a per-report decision, not a global default -- reconcile.py always
captures the full contact/compliance data into reconciled.json (so it stays
available for CRM/call-list use regardless), but each generator only prints
it into the client-facing document when you explicitly opt in for that
report. DNC- or litigator-flagged numbers are always labeled as such in that
section and must still be excluded from any outbound dialer/call list
regardless of whether this flag is set. See CHANGELOG.md (2026-09-12) for the
reasoning behind making this a flag rather than always-on or always-off.

## Report sections (in order)

**Investment Underwriting Brief:** Executive Summary -> [Contact & Outreach,
opt-in] -> Comps & ARV Analysis -> Renovation History Signals -> Listing
Language -> Strategy Recommendations -> Observations -> Demographics &
Economics -> Third-Party AI Insight (Dealio) -> Data Verification (open
items) -> Limitations & Disclaimer.

**Property Fact Sheet:** Property Identification -> Site & Structure ->
Valuation Data -> Exit-Strategy Scores (if provided by data source) -> Tax &
Assessment -> Financing / Lien on Record -> MLS Listing History -> Recorded
Status Flags -> [Ownership & Contact, opt-in] -> Source & Limitations.

**Loan Collateral Summary:** Collateral Risk Rating -> Subject Property ->
Collateral Valuation -> Existing Senior Lien Position -> Loan-to-Value
Analysis -> Distress Status Affecting Title & Timing -> Condition Notes ->
Underwriting Recommendation -> [Ownership & Contact, opt-in] -> Limitations &
Disclaimer.

## Setup

```bash
npm install docx
pip install pdfplumber --break-system-packages
```

See CHANGELOG.md for what's built, what's new/unvalidated, and what's planned.

## Git / GitHub

This repo is tracked on GitHub at
[writtinfool/newtree-reconciliation-pipeline](https://github.com/writtinfool/newtree-reconciliation-pipeline),
configured locally as the `dev` remote, tracking `main`:

```bash
git remote -v   # dev  https://github.com/writtinfool/newtree-reconciliation-pipeline.git
git push dev main
```
