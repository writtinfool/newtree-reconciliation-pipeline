# Changelog

## 2026-09-19
### Added
- **Commercial Centers rebuilt** — `fetch_demographics.py` gained
  `get_commercial_centers()` (nearest Home Depot/Lowe's/Costco/Walmart/
  Sam's Club + straight-line distance, via Places API (New) Text Search
  per chain name) and property lat/lng on the geocode result
  (`latitude`/`longitude`), wired into `fetch_demographics()`'s output as
  `commercial_centers`. See BACKLOG.md item 5. Compile-checked and the
  haversine/geocode path confirmed live without a key; the actual Places
  calls need `PLACES_API_KEY` set (Harold's machine only) before
  considered fully confirmed.
### Fixed
- **This is a rebuild, not new work** — this exact feature was already
  built once on 2026-08-22, but the git commit for it never happened
  (only `BACKLOG.md`'s original, not-yet-built item-5 text made it into
  commit `2297cd4`; the actual code was never committed at all). It was
  silently overwritten by a later session's edits to the same file
  sometime before 2026-09-12. Root-caused via `git show 2297cd4 --stat`
  and `git show 84945ee --stat`, neither of which touched the
  commercial-centers code. See the Notion "Reconciliation Pipeline" page
  and `BACKLOG.md` item 5 for the full story.

## 2026-09-14
### Added
- **`run_lender_ui.bat`** + a "Newtree Lender Matching" Desktop shortcut --
  launches `lender_matching/lender_ui.py` via `pythonw.exe` (no console
  window) with one double-click. Requested by Harold after testing the
  Tkinter UI and confirming it's the right direction.

### Fixed
- **Logan Investments' email typo** -- DATA_GAPS_2026-09-13.md had claimed
  this was corrected, but the actual Notion write was missed in the stage-1
  batch. Caught by testing `export_lenders.py` against live data (once
  Harold added a real `NOTION_API_KEY`) and fixed directly in Notion.
- Added `lender_matching/lenders.json` to `.gitignore` (generated output,
  same category as `reconciled*.json`).

## 2026-09-13
### Added
- **`lender_matching/`** -- separate from the property-reconciliation pipeline
  above. `export_lenders.py` pulls the reconciled Notion "Lender Directory"
  database (31 lenders, consolidated 2026-09-13 from 5 previously-duplicated
  Notion tables plus scattered local files) into `lenders.json` via the
  Notion REST API (stdlib `urllib` only, no new dependency); `match_lender.py`
  filters that JSON against a lead's loan type/state/credit score/loan amount,
  conservatively (a criterion only excludes a lender when the record
  explicitly says so -- an unset field never silently disqualifies), and
  always flags lenders still marked `Needs Verification` in Notion rather
  than treating them as reliable. See README.md's "Lender Matching" section.
  Needs its own `NOTION_API_KEY` (a real Notion integration token, separate
  from the OAuth connector used inside a Claude session) since it's meant to
  run unattended. Scheduled auto-refresh of `lenders.json` not yet built --
  see OPEN_ITEMS.md.
- **`lender_matching/lender_ui.py`** -- Tkinter desktop UI wrapping both
  scripts (a "Refresh from Notion" button, a search form, a results table,
  "Copy Results" to clipboard). Chosen over a local web page as the simpler
  starting point (no server to run); a web UI may still be built later.
- **Lender Directory schema: "Inactive" and "Lender Type" properties.**
  Added per Harold after reviewing the document-completeness findings: an
  `Inactive` checkbox (excluded from match_lender.py results by default, new
  `--include-inactive` flag to see them anyway) and a `Lender Type` select
  (Direct Lender / Referral Marketplace / Credit-Stacking Service). Per
  Harold, Referral Marketplace relationships (SBLS, South End Capital) exist
  specifically to refer deals in states he isn't licensed to broker directly
  -- match_lender.py tags these in its output but does not yet filter by
  state-licensing fit, since Newtree's own broker-state footprint isn't
  tracked anywhere yet (see OPEN_ITEMS.md).
- **`lender_matching/broker_footprint.json`** -- Newtree's own
  broker-state exclusion list (AZ, CA, ID, NV, NJ, NY, NC, ND, OR, SD, VT,
  WI), sourced from the company's BiggerPockets business profile. When
  `match_lender.py --state` is one of these, results now auto-restrict to
  `Referral Marketplace`-type lenders, per Harold: those relationships exist
  specifically so a client from a state he can't broker in directly isn't
  turned away. (Corrects an earlier misattribution: a state list found in
  Lima One Capital's intake form during the document review was Lima One's
  own restriction, not Newtree's footprint.)
- **Stage 1 Notion corrections applied** (see
  `lender_matching/DATA_GAPS_2026-09-13.md`): fixed Builders Finance's
  swapped loan-amount fields, corrected Kiavi's states-excluded list,
  cleared Atlantic Union's non-applicable credit-score field, enriched Cofi
  Capital, re-tagged Fund&Grow as Credit-Stacking Service, added Origin
  Mortgage (a signed-but-untracked broker relationship), added South End
  Capital and SBLS as Referral Marketplace entries, renamed "Revel" to
  "Reveal Lending" to match its own branding, and marked Relip Capital
  Inactive (Harold no longer works with them).

## 2026-09-12
### Added
- **Three report perspectives from one reconciled.json.** Added
  `fact_sheet/build_fact_sheet.js` (neutral, comprehensive property fact
  sheet -- everything on file, no strategy interpretation) and
  `collateral_summary/build_collateral_summary.js` (lender-perspective
  collateral risk assessment -- LTV against every valuation basis, a risk
  rating, an underwriting recommendation) as siblings to the existing
  `generate_brief.js`. Same brand palette (NAVY/ORANGE/GREEN/RED/GREY),
  same reconciled.json input, one script per document type per this repo's
  existing convention (see comps_template/, workflow_doc/) -- no shared lib
  introduced. Prompted by building one-off versions of these three views
  for a client property (113 Indigo Park Pl, Easley SC -- a pre-foreclosure,
  upside-down lead) and recognizing the pattern was worth generalizing into
  the pipeline rather than staying ad hoc.
- **`reconcile.py`: collateral/equity analysis.** New
  `compute_collateral_analysis()` computes equity-dollars, equity-%, and LTV
  against every available valuation basis (AVM, market value, wholesale
  value) using whichever loan balance is best available (estimated current
  balance, falling back to original amount), plus a HIGH/ELEVATED/MODERATE/
  LOWER risk rating and list-price-vs-payoff gap. Stored as
  `reconciled.collateral_analysis`; `None` when there's no loan balance or no
  valuation basis to compare it to, so `build_collateral_summary.js` can
  refuse to guess rather than print a misleading report.
- **`reconcile.py`: distress/motivation flag.** New
  `DISTRESSED_UPSIDE_DOWN_LEAD` flag fires when the CSV's PreForeclosure and
  UpsideDown columns are both true, noting the seller may be receptive to a
  short sale / subject-to / negotiated payoff. Uses the existing generic
  `flags` list, so it shows up in `generate_brief.js`'s Data Verification
  section automatically -- no template change needed there.
- **`parse_lead_csv()` extended** to capture fields the new views need that
  weren't previously read off this export format: full financing terms
  (loan type, interest rate, maturity date, estimated payment), site/
  structure detail (exterior, roof, heating, cooling, fireplace, garage,
  HOA, tax amount, subdivision, zoning, county), last-sale buyer/seller,
  full current+prior MLS listing detail (agent name/phone/email/office,
  list dates, days on market), all 16 distress/investor status flags (not
  just FreeAndClear/HighEquity), auction date, last notice date, retail/
  rental/wholesale scores when the export provides them, and Contact2-8
  names/emails as `additional_contacts`. Surfaced into reconciled.json as
  `property_details`, `financing_details`, `mls_details`, `status_flags`,
  `exit_scores`, and `last_sale_parties`.
- Two data-quality normalizations discovered while wiring this up, applied
  at parse time so they don't need repeating in every report generator:
  this export's `AuctionDate` uses `1/1/1900` as a null-date sentinel
  (normalized to `None`/"not scheduled"), and its `Stories` column has been
  observed reporting `0` for known multi-story homes (normalized to `None`/
  "not reported" rather than surfaced as fact).

### Changed -- contact info policy (deliberate, not a default flip)
- All three generators now accept `--include-contact-info`, off by default,
  gating a Contact & Outreach / Ownership & Contact section. Previously
  `generate_brief.js` simply never printed contact data at all (see its
  original file-header comment: "No contact/PII data is included -- that
  stays internal to the CRM / call list"). That blanket exclusion is now a
  per-report choice instead of a hardcoded one: the 113 Indigo Park Pl
  client reports needed contact info in the client's hands, but skip-traced
  contact data still has real reuse value internally (dialer lists, CRM)
  that a report generator shouldn't silently duplicate everywhere by
  default. Decided 2026-09-12 per Harold: this is an intentional policy and
  design change, not an oversight being corrected -- default stays off,
  opt in per report when a specific client/deal calls for it. DNC/litigator
  flags are always shown alongside a number when this section is printed,
  regardless of the flag.

### Fixed
- `generate_brief.js`: "Last Recorded Sale" showed a stray empty `()` when
  no Comps Report PDF was supplied (only a CSV). Now falls back to the
  CSV's own sale date and omits the parens entirely when no date is
  available from either source.
- All three generators: table rows could split across a page break
  mid-label (most visible in the Loan-to-Value Analysis table's longer
  scenario labels). Added `cantSplit: true` to every label/value table row.

## 2026-08-02
### Added
- Demographics & Economics section: Census geocoder (free) + ACS
  population/income/renter% (needs free Census key) + PEP population trend
  + BLS unemployment trend (free). Nearest-city fallback logic prefers
  Census Designated Place name over county-subdivision voting district
  (fixed a real bug: was showing "District 12" instead of a real place name
  like "Eden Isle" for unincorporated LA addresses).
- Comps & ARV Analysis: parses the full multi-page Dealio.pro comps table,
  dedupes, computes $/sqft low/median/high and ARV range. Validated against
  a real property's saved output (low/high matched to the dollar; median
  close). Flags when ARV is based mostly on listing price vs. confirmed
  closed sales.
- Renovation History Signals: 4 checks (loan activity, sale price history,
  tax assessment history, listing-description keyword scan) + a
  component-age baseline estimate (roof/HVAC/water heater/furnace/windows
  vs. typical service life). NEW LOGIC -- reimplemented from a spec in
  project memory, not recovered from prior source code (that code was never
  saved back to this repo/Drive in the prior session). Untested against a
  known-good output.
- Strategy Recommendations: scores 9 exit strategies (Wholesale, Fix & Flip,
  BRRRR, Buy & Hold, Short-Term Rental, Subject-To, Seller Financing, MLS
  Sale, Turnkey Rental) as decision support, "Insufficient data" reflecting
  data coverage not deal quality. Same caveat as renovation detection --
  first-draft heuristics, not validated against original output.
- Third-Party AI Insight section: accepts a pasted `--ai-insight <file.txt>`
  of Dealio Pro Ai's "Investment Insight" text (buy/hold verdict + bullets),
  shown separately from reconciled figures with a clear disclaimer.

### Known gaps / not yet built
- County assessor live-pull (Appendix B: multi-year valuation, conveyance
  history, millage rate) -- this existed in a prior session as *live browser
  automation* (Claude in Chrome), not reusable source code. Would need to be
  redone live per property, not "recovered."
- Demographics trends beyond population/unemployment (income, home value,
  rent history across ACS vintages) -- planned, not built.
- Metro area (CBSA) name, population, and straight-line distance -- planned,
  not built.
- Nearest incorporated city + its population, for unincorporated addresses
  -- planned, not built.
- Nearest commercial centers (Home Depot, Costco, Walmart, etc. + distance)
  via Places tool -- planned, not built.
- Permit office routing (incorporated -> city dept, unincorporated -> county/
  parish dept) -- planned: 5 county/parish entries first (Humboldt, Sonoma,
  Mendocino, Orleans, St. Tammany), city entries added on demand, live
  search as fallback for anything not yet in the table.
- Full automation (address in, report out, no live attendance) -- current
  state needs someone to manually pull the Property Profile PDF, Comps
  Report PDF, and skip-trace CSV from SendFuse/Dealio.pro (each a paid/
  metered click); a semi-automated version (Claude in Chrome driving those
  platforms live, still needs a human to approve paid clicks) is feasible
  with existing mapped workflows; true unattended automation would need
  either an API into those platforms or a scheduled browser-automation job
  plus a file-watching trigger.
