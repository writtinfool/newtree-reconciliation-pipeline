/**
 * Newtree Capital — Loan Collateral Summary generator
 * Reads reconciled property JSON (output of reconcile.py) and produces a
 * lender-perspective collateral risk assessment: existing senior lien
 * position, LTV against every valuation basis on hand, and an underwriting
 * recommendation. Sibling document to generate_brief.js / build_fact_sheet.js
 * -- same brand palette, same reconciled.json input, same
 * --include-contact-info opt-in flag (off by default).
 *
 * Relies on reconcile.py's compute_collateral_analysis() output
 * (reconciled.collateral_analysis). If that's absent -- no loan balance or
 * no valuation basis on record for this property -- the script exits with
 * an explanation rather than producing a misleading empty report.
 */

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, VerticalAlign,
} = require("docx");

const rawArgs = process.argv.slice(2);
const includeContactInfo = rawArgs.includes("--include-contact-info");
const positional = rawArgs.filter(a => a !== "--include-contact-info");
const inPath = positional[0];
const outPath = positional[1];
const companyName = positional[2] || "[Your Company Name]";

if (!inPath || !outPath) {
  console.error("Usage: node build_collateral_summary.js <reconciled.json> <output.docx> [\"Company Name\"] [--include-contact-info]");
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(inPath, "utf8"));
const r = data.reconciled;
const fields = r.fields || {};
const lc = data.raw_sources.lead_csv || {};
const pd = r.property_details || {};
const ca = r.collateral_analysis;

if (!ca) {
  console.error(
    "No collateral_analysis in this reconciled.json -- reconcile.py only computes it when a " +
    "loan balance (estimated_mortgage_balance or loan_amount) AND at least one valuation basis " +
    "(AVM, market value, or wholesale value) are both present. Re-run reconcile.py with a --csv " +
    "source that has this data, or use generate_brief.js / build_fact_sheet.js instead."
  );
  process.exit(1);
}

// ---- helpers (duplicated from generate_brief.js by repo convention) -----

const NAVY = "1F3864";
const ORANGE = "D97B29";
const GREEN = "1E7A34";
const RED = "B32424";
const GREY = "6B6B6B";
const LIGHT_GREY_SHADE = "F2F2F2";

function money(n) {
  if (n === null || n === undefined) return "N/A";
  return "$" + Math.round(n).toLocaleString("en-US");
}

function fieldValue(name, fallback = "N/A") {
  const f = fields[name];
  return f ? f.value : fallback;
}

function heading(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 240, after: 120 },
    shading: { type: ShadingType.CLEAR, fill: opts.fill || NAVY },
    children: [new TextRun({ text, bold: true, color: "FFFFFF", size: 22, font: "Calibri" })],
  });
}

function labelValueRow(label, value, opts = {}) {
  return new TableRow({
    cantSplit: true,
    children: [
      new TableCell({
        width: { size: 3600, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: LIGHT_GREY_SHADE },
        verticalAlign: VerticalAlign.CENTER,
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: label, bold: true, size: 19 })] })],
      }),
      new TableCell({
        width: { size: 6200, type: WidthType.DXA },
        verticalAlign: VerticalAlign.CENTER,
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({
          children: [new TextRun({ text: String(value), size: 19, color: opts.color || "000000", bold: !!opts.bold })],
        })],
      }),
    ],
  });
}

function bulletParagraph(text, opts = {}) {
  return new Paragraph({
    bullet: { level: 0 },
    spacing: { after: 100 },
    children: [new TextRun({ text, size: 20, color: opts.color || "000000" })],
  });
}

function noteParagraph(text) {
  return new Paragraph({ spacing: { before: 100 }, children: [
    new TextRun({ text, italics: true, size: 16, color: GREY }),
  ]});
}

function ratingColor(rating) {
  if (rating.startsWith("HIGH")) return RED;
  if (rating.startsWith("ELEVATED")) return ORANGE;
  if (rating.startsWith("MODERATE")) return ORANGE;
  return GREEN;
}

// ---- build content ------------------------------------------------------

const address = lc.property_full_address ||
  (data.raw_sources.property_profile && data.raw_sources.property_profile.site_address) ||
  "[Property Address]";

const primaryBasisName = ca.equity_by_basis.avm ? "avm" : Object.keys(ca.equity_by_basis)[0];
const primary = ca.equity_by_basis[primaryBasisName];
const primaryLabel = { avm: "AVM", market_value: "Market Value", wholesale_value: "Wholesale Value" }[primaryBasisName];

const sections = [];

sections.push(
  new Paragraph({
    spacing: { after: 60 },
    children: [new TextRun({ text: "LOAN COLLATERAL SUMMARY", bold: true, size: 32, color: NAVY })],
  }),
  new Paragraph({
    spacing: { after: 240 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ORANGE } },
    children: [new TextRun({ text: address, size: 24, color: "000000" })],
  }),
  new Table({
    width: { size: 9800, type: WidthType.DXA },
    rows: [
      labelValueRow("PREPARED BY", `${companyName} | Collateral Risk Assessment`),
      labelValueRow("REPORT GENERATED", new Date(data.generated_at).toLocaleDateString("en-US")),
      labelValueRow("DATA SOURCES RECONCILED", Object.keys(data.raw_sources).join(", ")),
    ],
  }),
);

// ---- Collateral Risk Rating ----
sections.push(
  heading("COLLATERAL RISK RATING", { fill: ratingColor(ca.risk_rating) }),
  new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({ text: ca.risk_rating, bold: true, size: 24, color: ratingColor(ca.risk_rating) })],
  }),
  new Paragraph({ spacing: { after: 120 }, children: [
    new TextRun({
      text: `Based on ${primaryLabel} of ${money(primary.value)}, the existing senior lien balance of ` +
        `${money(ca.senior_lien_balance_used)} (${ca.balance_basis === "estimated_mortgage_balance" ? "estimated current balance" : "original loan amount -- no current-balance estimate on file"}) ` +
        `represents a loan-to-value of ${primary.ltv_pct}%, leaving ` +
        `${primary.equity_dollars >= 0 ? `an estimated ${money(primary.equity_dollars)} (${primary.equity_pct}%) equity cushion` : `an estimated ${money(Math.abs(primary.equity_dollars))} (${Math.abs(primary.equity_pct)}%) negative-equity gap`}.`,
      size: 20,
    }),
  ]}),
);

// ---- Subject Property ----
sections.push(
  heading("SUBJECT PROPERTY"),
  new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
    labelValueRow("Address", address),
    labelValueRow("Property type", `${fieldValue("year_built")} build`),
    labelValueRow("Size", `${fieldValue("square_feet")} sq ft, ${fieldValue("bedrooms")} bed / ${fieldValue("bathrooms")} bath on a ${fieldValue("lot_sqft")} sq ft lot`),
  ]}),
);

// ---- Collateral Valuation ----
const basisRows = Object.entries(ca.equity_by_basis).map(([name, v]) => {
  const label = { avm: "Automated Valuation (AVM)", market_value: "Market Value (model)", wholesale_value: "Wholesale Value (model)" }[name] || name;
  return labelValueRow(label, `${money(v.value)}  —  LTV ${v.ltv_pct}%, equity ${money(v.equity_dollars)} (${v.equity_pct}%)`);
});
sections.push(
  heading("COLLATERAL VALUATION"),
  new Table({ width: { size: 9800, type: WidthType.DXA }, rows: basisRows }),
  noteParagraph("Recommend ordering a broker price opinion (BPO) or full appraisal before relying on any figure above for a lending decision -- all values here are model-derived, not independently verified."),
);

// ---- Existing Senior Lien Position ----
const fd = r.financing_details || {};
sections.push(
  heading("EXISTING SENIOR LIEN POSITION"),
  new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
    labelValueRow("Lienholder", fd.loan_lender_name || "N/A"),
    labelValueRow("Lien type", fd.loan_type ? `${fd.loan_type} first mortgage` : "N/A"),
    labelValueRow("Original amount", money(fd.loan_amount)),
    labelValueRow("Interest rate", fd.mortgage_interest_rate ? `${fd.mortgage_interest_rate}%` : "N/A"),
    labelValueRow("Recorded", fd.loan_recording_date || "N/A"),
    labelValueRow("Maturity", fd.loan_maturity_date || "N/A"),
    labelValueRow("Estimated current balance", money(fd.estimated_mortgage_balance)),
    labelValueRow("Estimated monthly debt service", money(fd.estimated_mortgage_payment)),
    labelValueRow("Priority", "Senior -- any new position would be junior unless this lien is paid off or subordinated"),
  ]}),
);

// ---- Loan-to-Value scenarios (existing balance, plus 5%/10% of primary
// basis as illustrative junior-position add-ons -- proportional so this
// generalizes across property values instead of hardcoded dollar steps) --
const juniorSteps = [0.05, 0.10];
const scenarioRows = [
  labelValueRow("Scenario", "Combined Debt", "LTV vs. " + primaryLabel, { bold: true }),
  labelValueRow("Existing senior lien only", money(ca.senior_lien_balance_used), `${primary.ltv_pct}%`),
  ...juniorSteps.map(step => {
    const junior = Math.round(primary.value * step);
    const combined = ca.senior_lien_balance_used + junior;
    const ltv = Math.round((combined / primary.value) * 1000) / 10;
    return labelValueRow(
      `Senior lien + hypothetical ${money(junior)} junior position (${Math.round(step * 100)}% of ${primaryLabel})`,
      money(combined), `${ltv}%`
    );
  }),
];
sections.push(
  heading("LOAN-TO-VALUE ANALYSIS"),
  new Table({ width: { size: 9800, type: WidthType.DXA }, rows: scenarioRows }),
  new Paragraph({ spacing: { before: 100 }, children: [
    new TextRun({
      text: primary.ltv_pct >= 65
        ? "There is little to no room for additional secured lending against this property at a conventional hard-money threshold (typically 65–75% ATV/ARV) without a full payoff/refinance of the existing lien."
        : "There may be room for a junior position within conventional hard-money thresholds (typically 65–75% ATV/ARV), subject to full underwriting and the senior lienholder's consent to a subordinate lien.",
      size: 20,
    }),
  ]}),
);

// ---- Distress Status Affecting Title & Timing ----
const sf = r.status_flags || {};
if (sf.PreForeclosure || sf.UpsideDown || r.auction_date) {
  sections.push(
    heading("DISTRESS STATUS AFFECTING TITLE & TIMING", { fill: RED }),
    ...(sf.PreForeclosure ? [bulletParagraph(`Pre-foreclosure flag: active, last notice dated ${r.last_notice_date || "unknown"}`, { color: RED })] : []),
    ...(sf.UpsideDown ? [bulletParagraph("Upside-down flag: active", { color: RED })] : []),
    bulletParagraph(`Formal foreclosure sale / auction date on record: ${r.auction_date || "not scheduled (no date on file)"}`),
    bulletParagraph("A rush title search is warranted before any funding commitment to confirm current lien balances, arrears, and whether a Notice of Default or lis pendens has been filed since this data was pulled."),
  );
}

// ---- Condition Notes ----
const desc = (r.mls_details || {}).mls_description_text;
sections.push(
  heading("CONDITION NOTES"),
  new Paragraph({ spacing: { after: 100 }, children: [
    new TextRun({
      text: desc
        ? `No physical inspection is on file. The most recent MLS listing description reads: "${desc}" This is marketing language from the listing agent, not an independent condition assessment, and should be verified before underwriting.`
        : "No physical inspection or listing description is on file for this property. Verify condition before underwriting.",
      size: 20,
    }),
  ]}),
);

// ---- Underwriting Recommendation ----
sections.push(
  heading("UNDERWRITING RECOMMENDATION", { fill: ORANGE }),
  ...(primary.ltv_pct >= 100
    ? [bulletParagraph("Do not underwrite this property as stand-alone collateral for a new or junior loan at current balances -- there is no equity margin.")]
    : primary.ltv_pct >= 80
    ? [bulletParagraph("Underwrite conservatively -- the equity cushion is thin relative to typical hard-money thresholds. A junior position would need strong compensating factors.")]
    : [bulletParagraph("Equity cushion supports further underwriting at a conservative advance rate, subject to full verification below.")]
  ),
  bulletParagraph(`Obtain a current payoff statement from ${fd.loan_lender_name || "the lienholder"} and a BPO/appraisal before any commitment.`),
  bulletParagraph("Confirm no additional junior liens, HOA liens, or tax liens have attached since this data was pulled, especially given any distress flags above."),
);

// ---- Ownership & Contact (opt-in only) ----
if (includeContactInfo) {
  const contacts = lc.contacts || [];
  const rows = [labelValueRow("Owner of record", lc.owner_name || "N/A")];
  contacts.forEach((c, i) => {
    const flags = [c.dnc ? "DNC" : null, c.litigator ? "Litigator" : null].filter(Boolean);
    rows.push(labelValueRow(`Phone ${i + 1}${c.type ? ` (${c.type})` : ""}`, c.phone + (flags.length ? `  — ${flags.join(", ")}` : ""), flags.length ? { color: RED, bold: true } : {}));
    if (c.email) rows.push(labelValueRow(`Email (Phone ${i + 1})`, c.email));
  });
  sections.push(
    heading("OWNERSHIP & CONTACT", { fill: GREY }),
    new Table({ width: { size: 9800, type: WidthType.DXA }, rows }),
    noteParagraph("Included because this report was generated with --include-contact-info; the tool's default omits this section."),
  );
}

sections.push(
  new Paragraph({ spacing: { before: 300, after: 100 }, children: [
    new TextRun({ text: "Limitations & Disclaimer", bold: true, size: 20, color: NAVY }),
  ]}),
  new Paragraph({ spacing: { after: 80 }, children: [
    new TextRun({
      text: `This summary is a screening-level risk assessment based on third-party aggregated data and is not a substitute for a title search, appraisal, or formal underwriting file. Figures are estimates and subject to change. Prepared by ${companyName} for internal use.`,
      size: 16, color: GREY,
    }),
  ]}),
);

const doc = new Document({
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 }, margin: { top: 900, bottom: 900, left: 1000, right: 1000 } },
    },
    children: sections,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log("Wrote", outPath);
});
