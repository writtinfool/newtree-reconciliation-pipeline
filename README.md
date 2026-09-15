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

### Running all three reports for a client (PowerShell)

`run_client_reports.ps1` wraps the four commands above into one call. It's a
generic, reusable entry point -- not tied to any one client -- so this is the
normal way to produce a client's report set, rather than writing a fresh
one-off script per client:

```powershell
.\run_client_reports.ps1 -Csv "G:\My Drive\...\Clients\<Client>\lpp-export-<uuid>\lpp-export-<uuid>.csv"

# optional: explicit output dir, custom company name, contact info on
.\run_client_reports.ps1 -Csv $csv -OutDir $outDir -CompanyName "Newtree Capital Resources LLC" -IncludeContactInfo
```

`-OutDir` defaults to the CSV's own folder, and `reconciled.json` is written
there too (not into the repo) since export folders are meant to be
self-contained per deal.

Add `-Pdf` to also convert each generated docx to PDF via a local LibreOffice
headless install (`soffice --headless --convert-to pdf`). This is a direct
render of the docx as authored -- use it instead of opening the docx in
Google Docs, whose own docx importer can badly mangle table layout.

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

## Lender Matching (separate from the reconciliation pipeline above)

`lender_matching/` reads the Notion "Lender Directory" database (the
reconciled canonical lender list, see CHANGELOG.md 2026-09-13) and matches a
lead's criteria against it.

```bash
python3 lender_matching/export_lenders.py         # pulls latest from Notion -> lenders.json
python3 lender_matching/match_lender.py --loan-type dscr --state NY --credit-score 660 --loan-amount 350000
```

`export_lenders.py` needs its own Notion integration token (`NOTION_API_KEY`
in `.env`) -- this is separate from the OAuth connector used inside a Claude
session, since this script is meant to run unattended (e.g. a scheduled
task). See the docstring at the top of `export_lenders.py` for the one-time
setup steps. `NOTION_LENDERS_DATA_SOURCE_ID` is already pre-filled with the
current database's id.

`match_lender.py` filters conservatively -- see its docstring for exactly
what counts as a disqualifier vs. an "unconfirmed, not excluded" gap. It
never silently drops lenders flagged `Needs Verification` in Notion; it
always marks them in the output instead. It returns every lender that
qualifies, not just one -- the point is a shortlist to reach out to, not a
single recommendation.

`lender_matching/broker_footprint.json` lists the states Newtree cannot
broker in directly (source: the company's BiggerPockets business profile).
When `--state` is one of those, `match_lender.py` automatically restricts
results to `Referral Marketplace`-type lenders (SBLS, South End Capital) --
the only path to still help a client in a state Harold isn't licensed to
broker in himself -- and prints a note explaining why direct lenders were
excluded from that particular search.

### Desktop UI

```bash
python3 lender_matching/lender_ui.py
```

A Tkinter window wrapping both scripts: a "Refresh from Notion" button and a
search form (loan type / state / credit score / loan amount) that lists
every matching lender in a table, with a "Copy Results" button for pasting
a plain-text list elsewhere. No server to run; works offline once
`lenders.json` exists.

A desktop shortcut ("Newtree Lender Matching") launches it directly via
`run_lender_ui.bat` (repo root) -- no terminal needed day to day. The batch
file calls `pythonw.exe` explicitly (no console window) at a hardcoded path
matching this machine's Python 3.14 install; update that path if Python
ever gets reinstalled elsewhere.

Not yet built: automatic scheduled refresh of `lenders.json` (logged in
OPEN_ITEMS.md), and folding this into `run_client_reports.ps1` as a fourth
report type.

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
