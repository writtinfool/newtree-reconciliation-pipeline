BACKLOG
Demographics & Economics — Backlog
Six items scoped in detail (agreed approach for each) but not yet built.
Logged here on 2026-08-22 per Harold; not started — no code changes in
this pass. fetch_demographics.py's STATUS block and CHANGELOG.md's
"Known gaps" section reference these at a higher level; this file is the
detailed spec to build from when picked up.
1. CBSA (Metro/Micropolitan Area) Name & Population
The Census Geocoder response already returns this — it's just not being
read yet. Needs one field pulled from the existing geocoder response,
plus one additional ACS call at the CBSA geography level.
This was originally scoped to also pull from PEP data. Given the PEP
diagnostic run this session (diagnose_pep.py; see the NOTE in
fetch_demographics.py — of vintages 2018–2024, only 2019 returns real
data via the public API), budget time to run that same diagnostic at the
metro/CBSA level before assuming PEP will work there — or just default
straight to the ACS-vintage-comparison approach already proven working
for the county-level trend (get_population_trend()).
2. Distance from Property to Metro Area
Needs the metro's principal-city coordinates plus a distance calculation
from the property's coordinates (already available from geocoding).
Agreed approach: straight-line distance for now. Drive-time is deferred
as a later add-on, since it needs a separate routing API.
3. Nearest Incorporated City
Distinct from the CDP fallback already built and confirmed working
("Eden Isle" for 84 Inlet Dr) — that fallback only reports what
contains the address point; it doesn't do a proximity search. This
item needs a genuine nearest-other-place search via the Places tool,
two-step: find the nearest incorporated city by name, then pull its ACS
population.
4. Historical Trends Beyond Population
Income, home value, and rent trends — currently only population trend is
built. Reuses the exact ACS-vintage-comparison pattern already proven
working (2018 vs. 2023 in get_population_trend()), just applied to
more variables.
5. Commercial Centers
Nearest Home Depot, Lowe's, Costco, Walmart, and Sam's Club, with
distance to each. Uses the Places tool — no new API key needed beyond
what's already required for item 3.
6. Permit Office Routing
No nationwide API for this — needs a curated table: incorporated
addresses route to the city building department; unincorporated
addresses route to the county/parish. Agreed build order: just the 5
active counties/parishes first, as county-level entries —
Humboldt County, CA
Sonoma County, CA
Mendocino County, CA
Orleans Parish, LA
St. Tammany Parish, LA
City-level entries added incrementally only when a deal actually lands
in one — not built exhaustively upfront.
Suggested starting points
#1 (CBSA) or #5 (Commercial Centers) are the most natural next picks —
#5 especially, since it needs no new API key and carries none of the PEP
availability uncertainty that #1 does.