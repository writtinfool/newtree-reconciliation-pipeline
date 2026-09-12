/**
 * Newtree Capital — Property Fact Sheet generator
 * Reads reconciled property JSON (output of reconcile.py) and produces a
 * neutral, comprehensive property fact sheet: everything on file, organized
 * by category, with NO strategy recommendation or investment interpretation
 * (that's what generate_brief.js is for). Sibling document to
 * generate_brief.js -- same brand palette, same reconciled.json input,
 * same --include-contact-info opt-in flag (off by default).
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
  console.error("Usage: node build_fact_sheet.js <reconciled.json> <output.docx> [\"Company Name\"] [--include-contact-info]");
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(inPath, "utf8"));
const r = data.reconciled;
const fields = r.fields || {};
const lc = data.raw_sources.lead_csv || {};
const pd = r.property_details || {};
const fd = r.financing_details || {};
const md = r.mls_details || {};
const sf = r.status_flags || {};
const vb = r.valuation_bases || {};

// ---- helpers (duplicated from generate_brief.js by repo convention --
// each doc generator here is self-contained, no shared lib) -------------

const NAVY = "1F3864";
const ORANGE = "D97B29";
const GREY = "6B6B6B";
const RED = "B32424";
const LIGHT_GREY_SHADE = "F2F2F2";

function money(n) {
  if (n === null || n === undefined) return "N/A";
  return "$" + Math.round(n).toLocaleString("en-US");
}

function fieldValue(name, fallback = "N/A") {
  const f = fields[name];
  if (!f) return fallback;
  return f.value;
}

function heading(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 240, after: 120 },
    shading: { type: ShadingType.CLEAR, fill: opts.fill || NAVY },
    children: [
      new TextRun({ text, bold: true, color: "FFFFFF", size: 22, font: "Calibri" }),
    ],
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

function noteParagraph(text) {
  return new Paragraph({ spacing: { before: 100 }, children: [
    new TextRun({ text, italics: true, size: 16, color: GREY }),
  ]});
}

// ---- build content ------------------------------------------------------

const address = lc.property_full_address ||
  (data.raw_sources.property_profile && data.raw_sources.property_profile.site_address) ||
  "[Property Address]";

const sections = [];

sections.push(
  new Paragraph({
    spacing: { after: 60 },
    children: [new TextRun({ text: "PROPERTY FACT SHEET", bold: true, size: 32, color: NAVY })],
  }),
  new Paragraph({
    spacing: { after: 240 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ORANGE } },
    children: [new TextRun({ text: address, size: 24, color: "000000" })],
  }),
  new Table({
    width: { size: 9800, type: WidthType.DXA },
    rows: [
      labelValueRow("PREPARED BY", `${companyName} | Data-Reconciled Property Fact Sheet`),
      labelValueRow("REPORT GENERATED", new Date(data.generated_at).toLocaleDateString("en-US")),
      labelValueRow("DATA SOURCES RECONCILED", Object.keys(data.raw_sources).join(", ")),
    ],
  }),
  noteParagraph("This fact sheet presents reconciled and as-reported third-party data organized by category. It does not include a strategy recommendation or investment interpretation -- see the Investment Underwriting Brief for that analysis."),
);

// ---- 1. Property Identification ----
sections.push(
  heading("1. PROPERTY IDENTIFICATION"),
  new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
    labelValueRow("Property address", address),
    labelValueRow("County", pd.county || "N/A"),
    labelValueRow("Subdivision", pd.subdivision || "N/A"),
    labelValueRow("Zoning", pd.zoning || "N/A"),
  ]}),
);

// ---- 2. Site & Structure ----
sections.push(
  heading("2. SITE & STRUCTURE"),
  new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
    labelValueRow("Bedrooms", fieldValue("bedrooms")),
    labelValueRow("Bathrooms", fieldValue("bathrooms")),
    labelValueRow("Living area", `${fieldValue("square_feet")} sq ft`),
    labelValueRow("County building area (total structure)", r.county_building_area_sqft ? `${r.county_building_area_sqft} sq ft` : "N/A"),
    labelValueRow("Lot size", `${fieldValue("lot_sqft")} sq ft`),
    labelValueRow("Year built", fieldValue("year_built")),
    labelValueRow("Stories", pd.stories || "N/A"),
    labelValueRow("Exterior", pd.exterior || "N/A"),
    labelValueRow("Roof", [pd.roof, pd.roof_shape].filter(Boolean).join(", ") || "N/A"),
    labelValueRow("Heating", pd.heating || "N/A"),
    labelValueRow("Air conditioning", pd.air_conditioning || "N/A"),
    labelValueRow("Fireplace(s)", pd.fireplace || "N/A"),
    labelValueRow("Garage", pd.garage || "N/A"),
    labelValueRow("HOA", pd.hoa ? `Yes — ${pd.hoa_fee ? money(pd.hoa_fee) : "amount N/A"}${pd.hoa_fee_frequency ? "/" + pd.hoa_fee_frequency.toLowerCase() : ""}` : "No / not on file"),
    labelValueRow("School district", pd.school_district || "N/A"),
  ]}),
);

// ---- 3. Valuation Data ----
const priceSqft = pd.price_per_sqft ? `$${pd.price_per_sqft.toFixed(2)}` : "N/A";
sections.push(
  heading("3. VALUATION DATA (AS REPORTED)"),
  new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
    labelValueRow("Automated Valuation (AVM)", money(vb.comps_avm || vb.csv_avm)),
    labelValueRow("Market Value (model)", money(vb.csv_market_value)),
    labelValueRow("Wholesale Value (model)", money(lc.wholesale_value)),
    labelValueRow("Rental estimate (range)", (lc.rental_estimate_low && lc.rental_estimate_high) ? `${money(lc.rental_estimate_low)} – ${money(lc.rental_estimate_high)} / month` : "N/A"),
    labelValueRow("Last sale price / date", fields.last_sale_price ? `${money(fields.last_sale_price.value)} (${lc.last_sales_date || "date N/A"})` : "N/A"),
    labelValueRow("Price per sq ft at last sale", priceSqft),
  ]}),
);

// ---- Exit scores, if present on this export ----
if (r.exit_scores && Object.keys(r.exit_scores).length) {
  const es = r.exit_scores;
  sections.push(
    heading("EXIT-STRATEGY SCORES (AS PROVIDED BY DATA SOURCE)", { fill: GREY }),
    new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
      ...(es.retail_score ? [labelValueRow("Retail score", es.retail_score)] : []),
      ...(es.rental_score ? [labelValueRow("Rental score", es.rental_score)] : []),
      ...(es.wholesale_score ? [labelValueRow("Wholesale score", es.wholesale_score)] : []),
    ]}),
    noteParagraph("These are the data provider's own scores, shown as-is -- not independently computed or endorsed here."),
  );
}

// ---- 4. Tax & Assessment ----
sections.push(
  heading("4. TAX & ASSESSMENT"),
  new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
    labelValueRow("Tax-assessed value", money(vb.csv_tax_assessed || vb.property_profile_assessed)),
    labelValueRow("Annual property tax", money(pd.tax_amount)),
  ]}),
);

// ---- 5. Financing / Lien on Record ----
if (Object.keys(fd).length) {
  sections.push(
    heading("5. FINANCING / LIEN ON RECORD"),
    new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
      labelValueRow("Number of recorded loans", fd.number_of_loans ?? "N/A"),
      labelValueRow("Lender", fd.loan_lender_name || "N/A"),
      labelValueRow("Loan type", fd.loan_type || "N/A"),
      labelValueRow("Interest rate", fd.mortgage_interest_rate ? `${fd.mortgage_interest_rate}%` : "N/A"),
      labelValueRow("Original loan amount", money(fd.loan_amount)),
      labelValueRow("Recording date", fd.loan_recording_date || "N/A"),
      labelValueRow("Maturity date", fd.loan_maturity_date || "N/A"),
      labelValueRow("Estimated current balance", money(fd.estimated_mortgage_balance)),
      labelValueRow("Estimated monthly payment", money(fd.estimated_mortgage_payment)),
      labelValueRow("Loan-to-value (balance / AVM)", fd.ltv_percent || "N/A"),
    ]}),
  );
}

if (r.last_sale_parties && (r.last_sale_parties.buyer || r.last_sale_parties.seller)) {
  sections.push(
    new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
      labelValueRow("Last sale — buyer", r.last_sale_parties.buyer || "N/A"),
      labelValueRow("Last sale — seller", r.last_sale_parties.seller || "N/A"),
    ]}),
  );
}

// ---- 6. MLS Listing History ----
if (Object.keys(md).length) {
  sections.push(heading("6. MLS LISTING HISTORY"));
  if (md.mls_current_status) {
    sections.push(
      heading("Most recent listing", { fill: ORANGE }),
      new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
        labelValueRow("Status", md.mls_current_status),
        labelValueRow("List date", md.mls_current_list_date || "N/A"),
        labelValueRow("List price", money(md.mls_current_list_price)),
        labelValueRow("Listing agent", [md.mls_current_agent_name, md.mls_current_agent_office].filter(Boolean).join(", ") || "N/A"),
        labelValueRow("Agent contact", [md.mls_current_agent_phone, md.mls_current_agent_email].filter(Boolean).join(" / ") || "N/A"),
      ]}),
    );
  }
  if (md.mls_description_text) {
    sections.push(
      new Paragraph({ spacing: { before: 80, after: 80 }, children: [
        new TextRun({ text: "Listing remarks: ", bold: true, size: 18 }),
        new TextRun({ text: md.mls_description_text, size: 18 }),
      ]}),
    );
  }
  if (md.mls_prev_status) {
    sections.push(
      heading("Prior listing", { fill: ORANGE }),
      new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
        labelValueRow("Status", md.mls_prev_status),
        labelValueRow("List date", md.mls_prev_list_date || "N/A"),
        labelValueRow("Sold date", md.mls_prev_sold_date || "N/A"),
        labelValueRow("Days on market", md.mls_prev_days_on_market ?? "N/A"),
        labelValueRow("List price / Sale price", `${money(md.mls_prev_list_price)} / ${money(md.mls_prev_sale_price)}`),
        labelValueRow("Listing agent", md.mls_prev_list_agent_name || "N/A"),
        labelValueRow("Selling agent", md.mls_prev_sold_agent_name || "N/A"),
      ]}),
    );
  }
}

// ---- 7. Recorded Status Flags ----
if (Object.keys(sf).length) {
  sections.push(
    heading("7. RECORDED STATUS FLAGS"),
    new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
      labelValueRow("Flag", "Status", { bold: true }),
      ...Object.entries(sf).map(([k, v]) => labelValueRow(k, v ? "TRUE" : "false", v ? { color: RED, bold: true } : {})),
    ]}),
    new Table({ width: { size: 9800, type: WidthType.DXA }, rows: [
      labelValueRow("Last notice date", r.last_notice_date || "N/A"),
      labelValueRow("Auction date", r.auction_date || "Not scheduled (no date on file)"),
    ]}),
  );
}

// ---- 8. Ownership & Contact (opt-in only) ----
if (includeContactInfo) {
  const contacts = lc.contacts || [];
  const additional = lc.additional_contacts || [];
  const rows = [labelValueRow("Owner of record", lc.owner_name || "N/A")];
  contacts.forEach((c, i) => {
    const flags = [c.dnc ? "DNC" : null, c.litigator ? "Litigator" : null].filter(Boolean);
    rows.push(labelValueRow(`Phone ${i + 1}${c.type ? ` (${c.type})` : ""}`, c.phone + (flags.length ? `  — ${flags.join(", ")}` : ""), flags.length ? { color: RED, bold: true } : {}));
    if (c.email) rows.push(labelValueRow(`Email (Phone ${i + 1})`, c.email));
  });
  additional.forEach(c => {
    rows.push(labelValueRow("Additional contact", [c.name, c.email, c.phone].filter(Boolean).join(" — ")));
  });
  sections.push(
    heading("8. OWNERSHIP & CONTACT", { fill: GREY }),
    new Table({ width: { size: 9800, type: WidthType.DXA }, rows }),
    noteParagraph("Numbers marked DNC or Litigator must be excluded from any outbound dialer/call list. Included because this report was generated with --include-contact-info; the tool's default omits this section."),
  );
}

sections.push(
  new Paragraph({ spacing: { before: 300, after: 100 }, children: [
    new TextRun({ text: "Source & Limitations", bold: true, size: 20, color: NAVY }),
  ]}),
  new Paragraph({ spacing: { after: 80 }, children: [
    new TextRun({
      text: `This fact sheet presents third-party aggregated data as of the report date above and has not been independently verified against the county recorder, a title report, or a physical inspection unless noted. Figures are estimates and subject to change. Prepared by ${companyName}.`,
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
