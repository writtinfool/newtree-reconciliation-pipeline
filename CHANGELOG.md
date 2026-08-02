# Changelog

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
