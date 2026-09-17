# Multi-Strategy Expansion — Notes

Cross-cutting, forward-looking notes on generalizing the reconciliation
pipeline and report generator beyond fix-and-flip. Originated in a
separate Claude.ai chat session (2026-09) that had no filesystem/git
access to this repo; captured here so it isn't stuck in that session's
own Project file store (`/projects/.../areas/multi-strategy-expansion.md`),
which this repo and Notion can't read. Logged 2026-09-17 per Harold;
nothing here has been built yet.

## Contact-info / DNC display policy for client reports

Settled in the same session, applies to `reconcile.py` / `generate_brief.js`
report output whenever contact info is included:

- Never suppress DNC/litigator status — always show it *alongside* contact
  info when contact info is included, not instead of it.
- Skip-trace still runs on every lead regardless of report gating —
  internal cost, good data to have either way.
- Gating happens at the report-generation step, not the data-collection
  step (i.e. don't skip skip-trace to save cost; withhold it from the
  rendered report if the client hasn't paid/isn't entitled to it).
- Billing: per-report, with no re-charge for identical duplicate copies.
- Internal (non-client) runs bypass the fee entirely.

**Status: not yet implemented.** This is a policy decision from
conversation, not yet reflected in `reconcile.py`, `generate_brief.js`,
or the Property Data Sourcing Guide. Needs to be built into the report
logic and documented in the guide.

## Architecture insight: BRRRR is not a separate template

Reconnects an earlier architecture decision (2026-08-22) that got
surfaced again in the 2026-09 session:

BRRRR isn't its own template — it's **Fix & Flip's front half stitched to
Turnkey's back half at the refinance event**. Conceptually:

- Acquisition → rehab → stabilization: same math as Fix & Flip.
- Refinance event: the hinge point where the deal switches from a
  flip-style exit assumption to a hold-style one.
- Post-refi hold: same math as Turnkey (cap rate, cash-on-cash, DSCR, NOI).

The one genuinely new piece of infrastructure needed is a shared
**Rental Hold module** — cap rate, cash-on-cash, DSCR, NOI — that both
BRRRR (post-refi) and Turnkey/Buy & Hold can call into, instead of each
strategy re-deriving those numbers separately.

**Status: designed on paper, not built.**

## Service reframe: information-analyst service

The 2026-09 session reframed the whole client-facing service as an
"information-analyst service delivering deal models to clients":

- Address in, pre-diligence report out.
- Covers all major strategies at 3-4 rehab tiers.
- Multiple perspectives per deal (e.g. flip vs. hold vs. BRRRR side by
  side), not just one strategy's numbers.
- Progressively refined as a client's offer firms up — a rough first pass
  early, more precision as the deal gets real.

This is also the source of the "real estate financial information analyst
and consultant" language already logged as the Consultant Scope Statement
in `OPEN_ITEMS.md` — same framing, two different conversations arriving
at it independently.

## Access model

Confirmed in the same session:

- Analyst-mediated, not self-serve — Harold (or Newtree) sits between the
  client and the report, not a client-facing self-service tool.
- Client sign-up required before reports are generated.
- Reports free during beta.
- Paid per-report after beta.
- Possible subscription tier later, for some clients (not all).

## Open items / not yet decided

- **Calculation-engine architecture decision** (blocks building the
  Rental Hold module): should strategy + rehab-tier be parameters into a
  single shared calculation engine, or should each strategy stay a
  separate template/fork? Needs a decision before the Rental Hold module
  gets built, since the answer changes how it's structured.
- **Build-order decision**: which side gets built first — the Excel
  financial-model side (client-facing workbooks/templates) or the
  reconciliation-pipeline/report-generator side (`reconcile.py` /
  `generate_brief.js`)? Not decided.
- **`product-templates/` file-deletion mystery**: flagged as unresolved in
  the 2026-09 session — files went missing from `product-templates/` at
  some point. Not investigated. Worth a `git log --diff-filter=D --
  product-templates/` pass to find when/what, next time someone's in the
  repo with git access.

## Where this lives

This file is the repo-side copy. The same content (condensed) is also in
the Notion "Reconciliation Pipeline (reconcile.py / GitHub)" page under
the "Contact-info / DNC policy" and "Multi-strategy expansion" sections —
keep both in sync if either gets updated, since they were written from
the same source material but aren't linked programmatically.
