// Builds Newtree_Client_Report_Production_Workflow.docx -- an internal
// process reference documenting the end-to-end steps used to produce
// the 4134 E 142nd St deliverable set (the first one run through this
// pipeline). Explicitly a first-pass / DRAFT document, matching the
// house style of Property_Data_Sourcing_Guide_3.docx (plain Word
// heading styles, not the client-facing navy/gold report branding).

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, AlignmentType, BorderStyle, ShadingType, HeadingLevel,
  convertInchesToTwip, LevelFormat, NumberFormat
} = require("docx");

const GREY = "595959";
const NAVY = "1F3864";
const NOTE_FILL = "FFF4CE";

function h1(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 120 } });
}
function h2(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 100 } });
}
function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 140, line: 268 },
    children: [new TextRun({ text, italics: opts.italics, bold: opts.bold, color: opts.color, size: opts.size ?? 21 })],
  });
}
function bullet(text, opts = {}) {
  return new Paragraph({
    bullet: { level: 0 },
    spacing: { after: 60, line: 260 },
    children: [new TextRun({ text, size: 21, bold: opts.bold, italics: opts.italics })],
  });
}
const ROLE_COLOR = { CLAUDE: "2E5EAA", HAROLD: "B15C00", BOTH: "6B3FA0" };
const ROLE_LABEL = { CLAUDE: "CLAUDE", HAROLD: "HAROLD", BOTH: "BOTH" };

function roleTag(role) {
  return new TextRun({ text: `  [${ROLE_LABEL[role]}]`, bold: true, size: 18, color: ROLE_COLOR[role] });
}

function numbered(text, num, role) {
  const runs = [
    new TextRun({ text: `${num}. `, bold: true, size: 21 }),
    new TextRun({ text, size: 21 }),
  ];
  if (role) runs.push(roleTag(role));
  return new Paragraph({ spacing: { after: 80, line: 260 }, children: runs });
}

function phaseOwner(text) {
  return new Paragraph({
    spacing: { after: 100 },
    children: [new TextRun({ text: "Who runs this phase: ", bold: true, italics: true, size: 19, color: GREY }),
               new TextRun({ text, italics: true, size: 19, color: GREY })],
  });
}

function roleRow(role, cells, header) {
  const fill = header ? "D9D9D9" : undefined;
  return new TableRow({
    children: cells.map((t, i) => new TableCell({
      width: { size: i === 0 ? 2600 : 6750, type: WidthType.DXA },
      shading: fill ? { type: ShadingType.CLEAR, fill } : undefined,
      margins: { top: 80, bottom: 80, left: 100, right: 100 },
      children: [new Paragraph({ children: [new TextRun({
        text: t, size: 20, bold: header, color: header ? undefined : undefined,
      })] })],
    })),
  });
}
function noteBox(text) {
  return new Table({
    width: { size: 9350, type: WidthType.DXA },
    rows: [new TableRow({ children: [new TableCell({
      shading: { type: ShadingType.CLEAR, fill: NOTE_FILL },
      margins: { top: 100, bottom: 100, left: 120, right: 120 },
      children: [new Paragraph({
        children: [new TextRun({ text, italics: true, size: 20, color: "5B4B00" })],
      })],
    })] })],
  });
}

const doc = new Document({
  sections: [{
    properties: { page: { margin: { top: 1000, bottom: 1000, left: 1080, right: 1080 } } },
    children: [
      new Paragraph({
        heading: HeadingLevel.TITLE,
        children: [new TextRun({ text: "Client Report Production Workflow", bold: true })],
      }),
      p("Newtree Capital Resources LLC — Internal Reference", { italics: true, color: GREY, after: 60 }),
      p("Status: DRAFT — first documented pass, written up after producing the pipeline's first live deliverable "
        + "(4134 E 142nd St). This is a snapshot of the steps as they were actually run, not a finished SOP. "
        + "Expect it to change as more deals go through it — update this document whenever the real workflow "
        + "diverges from what's written here, the same standing rule the Property Data Sourcing Guide uses.",
        { italics: true, size: 19, color: GREY, after: 260 }),

      h1("Kickoff Checklist — What Harold Sends to Start a Deal"),
      p("The shortest version: address + Prepared For name, plus confirmation the SendFuse/Dealio.pro session is "
        + "logged in. Everything else below is either pulled automatically or only needed in specific cases."),
      new Table({
        width: { size: 9350, type: WidthType.DXA },
        rows: [
          roleRow(null, ["Required", "Needed for"], true),
          roleRow(null, ["Subject property address (full street, city, state, ZIP)", "Everything in Phase 1 keys off this — SendFuse, Dealio.pro, county assessor, and the demographics pull."]),
          roleRow(null, ["Confirmation of SendFuse / Dealio.pro login", "The browser session has to be live and authenticated before Claude can pull anything."]),
          roleRow(null, ["\"Prepared For\" name (client / wholesaler)", "Report header and Client User Guide framing."]),
        ],
      }),
      new Paragraph({ spacing: { before: 160 } }),
      new Table({
        width: { size: 9350, type: WidthType.DXA },
        rows: [
          roleRow(null, ["Situational — only if not publicly discoverable", "Needed for"], true),
          roleRow(null, ["Asking/contract price", "Pulled automatically if the property is an active MLS listing Dealio.pro can see. Required from Harold for an off-market or wholesaler-sourced deal (e.g. 4134 E 142nd St)."]),
          roleRow(null, ["Any term sheet, contractor bid, or other negotiated terms already in hand", "Not needed for a standard Quick Screen — only relevant if the deal is upgrading straight to a Full Model."]),
          roleRow(null, ["Non-default screen thresholds", "Model defaults to $20,000 minimum profit / 15% minimum margin. Only mention this to override."]),
        ],
      }),
      p("Everything else — property specs, ownership, tax history, comps, rehab estimate inputs, demographic "
        + "data — Claude pulls directly once it has the address and a live logged-in session.", { after: 260 }),

      h1("Overview"),
      p("Producing one client-ready deliverable set touches nine phases, from raw data pull through the "
        + "post-delivery feedback call. Phases 1–2 happen live, in a browser session against SendFuse / "
        + "Dealio.pro / county assessor sites. Phases 3–7 build the actual deliverable files. Phases 8–9 are "
        + "packaging and sending. The two Bucket references below recur throughout — see the Property Data "
        + "Sourcing Guide and the bucket model for the full definitions."),
      bullet("Bucket 1 — Templates & Methodology: reusable, version-controlled in git (product-templates/)."),
      bullet("Bucket 2 — Client Deliverables: per-deal, goes to the client (Drive, PDF-first)."),
      bullet("Bucket 3 — Internal Working Files: per-deal, evidence/reasoning trail, never shared with a client."),

      h1("Roles at a Glance"),
      p("Every step below is tagged [CLAUDE], [HAROLD], or [BOTH]. Four kinds of things always fall to Harold, "
        + "no matter which phase they show up in — worth knowing up front rather than re-discovering per phase:"),
      new Table({
        width: { size: 9350, type: WidthType.DXA },
        rows: [
          roleRow(null, ["Interaction needed", "Why Claude can't do it alone"], true),
          roleRow(null, ["Logging into SendFuse / Dealio.pro", "Claude never enters credentials — the browser session needs Harold already signed in."]),
          roleRow(null, ["git commit / push", "device_bash can't run git reliably (file-lock/deletion limits) — must run in Harold's real PowerShell."]),
          roleRow(null, ["Emailing or sharing files with the actual client", "Sending on Harold's behalf to a third party needs explicit per-instance approval — Claude drafts/stages, Harold sends."]),
          roleRow(null, ["The feedback call itself", "A live phone conversation — Claude can prep the guide and log the notes afterward, not place the call."]),
        ],
      }),
      p("Everything else — pulling data once logged in, filling workbooks, writing the report, building support "
        + "documents, organizing files into the right folders — Claude can do end-to-end without Harold present, "
        + "as long as the browser session is live and the file locations are already set up.", { after: 260 }),

      h1("Phase 1 — Property Data Sourcing (live browser session)"),
      p("Tools: Claude in Chrome, logged into SendFuse and Dealio.pro. Reference: Property Data Sourcing Guide."),
      phaseOwner("Harold logs into SendFuse and Dealio.pro once at the start (or confirms he's already logged in); Claude drives everything after that."),
      numbered("Confirm logged into SendFuse and Dealio.pro in the connected Chrome session.", 1, "HAROLD"),
      numbered("Pull the SendFuse Property Profile (bed/bath/sqft, tax value, owner, loans, LTV, last sale). Cross-check ownership and current-loan claims against the county assessor — SendFuse has mislabeled these before.", 2, "CLAUDE"),
      numbered("Pull the Dealio.pro Comps Report and skip-trace CSV for the subject property.", 3, "CLAUDE"),
      numbered("Pull the county assessor record for the subject property (ownership, tax, legal description, transfer history) — the highest-trust source in the hierarchy.", 4, "CLAUDE"),
      noteBox("STANDING RULE: capture everything now. Dealio.pro's comps export is not retrievable after the "
        + "session ends — confirmed by testing on 4134 E 142nd St. Save any downloaded file immediately into "
        + "the deal's Internal Working Files folder; don't assume you can come back for it."),

      h1("Phase 2 — Comp Validation (live, same session as Phase 1)"),
      p("Reference: Property Data Sourcing Guide, Rule 1 (transaction-pair verification) and Rule 4 (rental/commercial reclassification)."),
      phaseOwner("Fully Claude, using the data already pulled in Phase 1 — no separate Harold action needed."),
      numbered("For every comp tagged by Dealio.pro as previously sold, check for a real transaction-pair price jump between two sales of the same property — not just the tag.", 1, "CLAUDE"),
      numbered("Cross-check buyer type, financing, and the listing's own description. Individual buyer + financed (FHA/conventional) + a description of completed renovation work = confirmed genuine retail-ARV.", 2, "CLAUDE"),
      numbered("Tag each comp as you go: Confirmed Genuine / Moderate Confidence / Excluded (e.g. same-week wholesale double-close) / Reclassified (rental or commercial exit, Rule 4).", 3, "CLAUDE"),
      numbered("Log every comp — kept and excluded alike — into the Internal Working Files workbook's Comp Validation Log tab in the same sitting. This live log is the durable record; a PDF alone is not.", 4, "CLAUDE"),
      numbered("Separately, capture the confirmed and moderate-confidence comps into the Comps Support Document template (Bucket 1) — this becomes a client-facing deliverable in Phase 6.", 5, "CLAUDE"),

      h1("Phase 3 — Demographic & Economic Context"),
      p("Tool: fetch_demographics.py (Census Geocoder + ACS 5-Year + BLS LAUS)."),
      phaseOwner("Fully Claude, as long as CENSUS_API_KEY is already set up (one-time setup Harold already did)."),
      numbered("Run fetch_demographics.py against the subject address. Requires CENSUS_API_KEY (set via a gitignored .env file next to the script; the script's own _load_dotenv() picks it up automatically).", 1, "CLAUDE"),
      numbered("Pull county and city-level population, population trend (ACS 5-Year vintage comparison — not PEP, which is unreliable per the script's own docstring), median household income, renter-occupied housing share, and unemployment rate.", 2, "CLAUDE"),
      numbered("Read these as marketability signals for the report: renter-occupancy for rental demand, population/unemployment stability for lender confidence, and the city/county income gap for buyer-pool context (workforce vs. luxury market).", 3, "CLAUDE"),

      h1("Phase 4 — Quick Screen Workbook"),
      p("Tool: xlsx skill, openpyxl. Source: Fix_Flip_Model_Template_QuickScreen_BLANK.xlsx (Bucket 1)."),
      phaseOwner("Fully Claude from Phase 1-3 data, unless a number isn't sourced anywhere public (e.g. a negotiated price only Harold knows) — then Harold supplies that one input."),
      numbered("Copy the blank template to a deal-specific filename.", 1, "CLAUDE"),
      numbered("Fill Assumptions (acquisition, property data, rehab total, holding costs, disposition, screen thresholds, as-is market check), Rehab Estimate (category-level buckets), Deal Screen (pulls from Assumptions), and Source Log (every source, report type, and pull date).", 2, "CLAUDE"),
      numbered("Supply any deal-specific figure not available from a public/pulled source — e.g. an asking price only known from a direct conversation with the wholesaler.", 3, "HAROLD"),
      numbered("Run recalc.py to populate cached formula values and catch errors (e.g. the #DIV/0! risk on a blank ARV, guarded with IFERROR) before anything ships.", 4, "CLAUDE"),
      numbered("Apply cell-level protection: yellow-fill cells (input convention) unlocked, everything else locked, sheet protection on, no password. This is now the default for every populated workbook, not just the blank template.", 5, "CLAUDE"),

      h1("Phase 5 — Report Writing"),
      p("Tool: docx skill (raw XML edit against the report template's existing structure)."),
      phaseOwner("Fully Claude to produce a draft; Harold's read-through before it ships is strongly recommended, not optional."),
      numbered("Sections, in order: title block (address, prepared-by/for, stage tag) → executive read → property & ownership (verified) → As-Is Market Check (Rule 5) → ARV & Comparable Sales Analysis → Neighborhood & Economic Context (Phase 3 data) → Rehab Estimate & Deferred Maintenance → Verdict → What a Full Model Adds → Assumptions & Open Items.", 1, "CLAUDE"),
      numbered("Match existing style conventions exactly (heading borders, table shading, callout boxes, source-citation lines) rather than introducing new formatting per section.", 2, "CLAUDE"),
      numbered("Validate with validate.py --original <source>, then visually confirm by rendering to PDF/JPG and reading each changed page before calling it done.", 3, "CLAUDE"),
      numbered("Read the finished draft before it goes to a client — Claude's own visual check catches rendering/formatting breaks, not factual or tone misjudgments.", 4, "HAROLD"),

      h1("Phase 6 — Comps Support Document"),
      p("Tool: docx skill (new document from the Bucket 1 template). Client-facing evidentiary backup for the ARV figure — this is what makes Phase 2's live logging worth doing."),
      phaseOwner("Fully Claude, from the data already logged in Phase 2."),
      numbered("Fill the template with the confirmed and moderate-confidence comps captured in Phase 2: address, sale-pair prices/dates, buyer type, financing, $/sqft, tier, and a one-line basis.", 1, "CLAUDE"),
      numbered("Excluded and reclassified comps stay out — those live in the Internal Working Files Comp Validation Log only.", 2, "CLAUDE"),

      h1("Phase 7 — Internal Working Files Log (Bucket 3)"),
      p("Tool: xlsx skill. Source: Newtree_Internal_Working_Files_Template.xlsx (Bucket 1)."),
      phaseOwner("Fully Claude if built live during Phase 2, as intended — a real interaction gap only opens up if this step gets skipped and has to be reconstructed later (as happened on 4134 E 142nd St)."),
      numbered("Field Source Log — one row per property fact, with its source, report type, and pull date.", 1, "CLAUDE"),
      numbered("Comp Validation Log — every comp evaluated, confirmed and excluded alike (built live in Phase 2, not reconstructed afterward).", 2, "CLAUDE"),
      numbered("Cross-Check Log — every public-record verification run against Dealio.pro/SendFuse data (e.g. owner correction, tax record match).", 3, "CLAUDE"),
      p("This workbook never leaves OneDrive's Internal Working Files folder for that deal — it is never copied to the Google Drive client-share folder.", { italics: true, color: GREY }),

      h1("Phase 8 — Package for Delivery"),
      h2("OneDrive — Newtree Deals\\[Deal Name]\\ (source of truth, everything lives here)"),
      bullet("Client Deliverable\\ — report (.docx + .pdf), protected Quick Screen workbook, Comps Support Document, Client User Guide (.docx + .pdf), Beta Feedback Call Guide & Survey form."),
      bullet("Internal Working Files\\ — the filled Internal Working Files log. Never copied elsewhere."),
      h2("Google Drive — Newtree Client Share\\[Deal Name]\\ (share-only, PDF-first mirror)"),
      bullet("Same client-facing files as above, PDF format only — no raw .docx report copy goes here, since two live formats of the same document invites version drift once either gets revised."),
      p("Editable sources (report .docx, comps/workbook masters) stay on OneDrive for revision; Google Drive is "
        + "the clean copy actually shared with the client's Gmail address.", { italics: true, color: GREY }),
      phaseOwner("Fully Claude for file placement, as long as both folders are already connected/granted; Harold approves the git commit/push separately (see Roles at a Glance)."),

      h1("Phase 9 — Delivery & Follow-Up"),
      phaseOwner("Client-facing send and the call itself are Harold's; Claude preps and logs around both."),
      numbered("Claude confirms the Google Drive deal folder is complete and current.", 1, "CLAUDE"),
      numbered("Share the folder (or the individual PDFs) with the client — an email or message to a third party, which needs Harold to actually send it.", 2, "HAROLD"),
      numbered("After the client has had time to review, place the follow-up call using the Beta Feedback Call Guide & Survey form.", 3, "HAROLD"),
      numbered("Claude can type up notes into the form's fields during or after the call, if Harold relays answers live or afterward — but Claude isn't on the call itself.", 4, "BOTH"),
      numbered("Log call outcomes/answers back into the Internal Working Files or wherever the beta program is tracking response data (not yet formalized as of this draft).", 5, "CLAUDE"),

      h1("Open Items in This Workflow"),
      bullet("Step 3 of Phase 9 (where feedback responses get tracked) isn't formalized yet."),
      bullet("No SQLite/cross-deal querying yet — workbook-first until more deals have run through this."),
      bullet("BRRRR/Turnkey variant of this workflow not yet built."),
      bullet("This document itself hasn't been run against a second deal yet — treat every step above as provisional until it has."),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("Newtree_Client_Report_Production_Workflow.docx", buf);
  console.log("written");
});
