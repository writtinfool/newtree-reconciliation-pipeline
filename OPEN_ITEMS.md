# Open Items — Cross-Cutting

Non-demographics, non-engineering items that came up in conversation and are
worth building later. See BACKLOG.md for the demographics/economics-specific
list.

## Consultant Scope Statement

Logged 2026-08-23 per Harold, not started.

A client-facing statement defining what Newtree Capital Resources LLC is and
isn't, to set expectations and limit liability:

- **Is:** a real estate financial information analyst and consultant.
- **Is not:** a full-service financial planner, financial advisor, or real
  estate agent/broker — plus whatever other specific disclosures Harold wants
  included (not yet itemized beyond the above).

Where this likely belongs once built: probably folded into (or alongside) the
Client User Guide, since that's the client's first-read orientation document,
rather than a standalone deliverable — but that's a layout decision for when
this actually gets drafted, not decided yet.

Worth flagging when this gets built: scope-of-service and liability-limiting
language is exactly the kind of thing that benefits from an actual attorney's
review before it goes out to clients — I can draft the substance and structure,
but I'm not a lawyer and shouldn't be the last check on wording that's meant
to limit legal liability.

## Lender Matching Script

Logged 2026-09-13 per Harold. **Built 2026-09-13**: `lender_matching/`
(export_lenders.py, match_lender.py, lender_ui.py — a Tkinter desktop UI).
See README.md's "Lender Matching" section and CHANGELOG.md 2026-09-13.

Still open:
- **Scheduled auto-refresh of `lenders.json`** — not built. Needs a Notion
  integration token (`NOTION_API_KEY` in .env, currently blank) before either
  the script or a Task Scheduler entry can run; registering the actual
  scheduled task was deliberately left for Harold to request explicitly
  (persistent system config change).
- **Term-sheet comparison fields** (rate range, points, max LTV/LTC) —
  deliberately deferred per Harold ("for now just a list to reach out to").
  The document-completeness review already surfaced real rate/LTV/points
  data for many lenders (see lender_matching/DATA_GAPS_2026-09-13.md) that
  could populate this once it's prioritized.
- **Web UI** — Harold said he likes web pages but wanted the Tkinter version
  as the easier starting point. A local web version (would need a small
  local server, e.g. Flask or http.server) is a possible follow-up, not
  started. Harold has since said (2026-09-13) he'd like something "useful
  project wide for all the reports as well as this picker" -- i.e. a shared
  front-end over reconcile.py + the three report generators + the lender
  matcher, not just the lender picker alone. He's experienced with web apps
  and fine running a local server; floated that it may eventually move to
  his own web hosting. Deliberately not scoped yet -- needs a real design
  pass (single page vs. per-report tabs, whether it replaces
  run_client_reports.ps1 or sits alongside it, file upload/download
  handling for PDFs/CSVs/.docx) before building anything.
- **Live website reconciliation pass** — logged 2026-09-14 per Harold, not
  started ("tomorrow or later"). For each active lender in the Lender
  Directory, locate and visit their actual website, reconcile it against
  what's in Notion, and update anything missing -- especially contact info
  (many records still show "no contact on file" even after the 2026-09-13
  document review, since that review only covered local files, not each
  lender's live site). Scope notes for whoever picks this up:
  - Pull the current lender list + Broker Page URLs from the live Notion
    database (or `lender_matching/lenders.json` after a fresh
    `export_lenders.py` run) rather than a static list here, since it will
    have moved on by the time this is picked up.
  - Skip `Inactive` records (currently just Relip Capital).
  - A few records have no Broker Page URL on file at all (e.g. Relip
    Capital, and originally Alta Financial before this session's fixes) --
    those need the website found first, not just visited.
  - Where a lender's site materially conflicts with what document review
    already found (e.g. different rates/criteria than the confidential PDFs
    on file), flag it rather than silently overwriting -- same conservative
    approach used in the 2026-09-13 corrections
    (lender_matching/DATA_GAPS_2026-09-13.md).
- **Newtree's own broker-state footprint** — BUILT 2026-09-13.
  `lender_matching/broker_footprint.json` holds the excluded-states list,
  sourced from Newtree's own BiggerPockets business profile
  (https://www.biggerpockets.com/business/page/9602): AZ, CA, ID, NV, NJ,
  NY, NC, ND, OR, SD, VT, WI. (Correction: the Lima One intake-form state
  list found during the document review is Lima One's own lending
  restriction, NOT Newtree's footprint -- that was a misattribution in the
  original DATA_GAPS write-up.) `match_lender.py` now auto-restricts
  results to `Referral Marketplace`-type lenders when `--state` is on this
  list, with an explanatory note printed. Not yet done: keeping this file in
  sync if Newtree's licensing footprint changes -- it's a static JSON file,
  not pulled from the BiggerPockets page live.
