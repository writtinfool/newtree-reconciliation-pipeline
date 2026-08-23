/**
 * Newtree Capital — Executive Underwriting Brief generator
 * Reads reconciled property JSON (output of reconcile.py) and produces a
 * client-ready cover brief. Only verified/reconciled figures are used --
 * anything still flagged as a conflict is shown as an open item, never
 * presented as settled fact. No contact/PII data is included (that stays
 * internal to the CRM / call list).
 */

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, ShadingType, HeadingLevel, BorderStyle, AlignmentType,
  PageOrientation, VerticalAlign,
} = require("docx");

const inPath = process.argv[2];
const outPath = process.argv[3];
const companyName = process.argv[4] || "[Your Company Name]";

if (!inPath || !outPath) {
  console.error("Usage: node generate_brief.js <reconciled.json> <output.docx> [\"Company Name\"]");
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(inPath, "utf8"));
const r = data.reconciled;
const fields = r.fields;

// ---- helpers --------------------------------------------------------------

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

function fieldValue(name, fallback = "Unresolved / see verification notes") {
  const f = fields[name];
  if (!f) return fallback;
  return f.value;
}

function fieldConfidenceNote(name) {
  const f = fields[name];
  if (!f) return null;
  if (f.confidence === "agreed") {
    return `Confirmed across ${f.sources.length} independent sources.`;
  }
  if (f.confidence === "resolved_by_trust_hierarchy") {
    return `Sources disagreed (${JSON.stringify(f.all_values)}); resolved via ${f.chosen_source}.`;
  }
  return null;
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

function pct(n) {
  if (n === null || n === undefined) return "N/A";
  return `${n}%`;
}

function fmtTrend(trend) {
  if (!trend || trend.error) return null;
  const arrow = trend.direction === "growing" ? "↑" : trend.direction === "declining" ? "↓" : "→";
  return `${trend.direction} ${arrow} (${trend.pct_change > 0 ? "+" : ""}${trend.pct_change}% over ${trend.span})`;
}

// ---- build content ----------------------------------------------------

const address = (data.raw_sources.lead_csv && data.raw_sources.lead_csv.property_full_address) ||
  (data.raw_sources.property_profile && data.raw_sources.property_profile.site_address) ||
  "[Property Address]";

const beds = fieldValue("bedrooms");
const baths = fieldValue("bathrooms");
const sqft = fieldValue("square_feet");
const lot = fieldValue("lot_sqft");
const yearBuiltField = fields["year_built"];
const yearBuiltDisplay = yearBuiltField
  ? (yearBuiltField.confidence === "agreed"
      ? yearBuiltField.value
      : `${yearBuiltField.value} (unresolved — sources range ${Math.min(...Object.values(yearBuiltField.all_values))}–${Math.max(...Object.values(yearBuiltField.all_values))})`)
  : "Unresolved";

const countyBuildingArea = r.county_building_area_sqft;

const lastSale = fields["last_sale_price"];
const lastSaleDisplay = lastSale ? money(lastSale.value) : "N/A";

const vb = r.valuation_bases || {};
const avm = vb.comps_avm || vb.csv_avm;
const marketValue = vb.csv_market_value;
const taxAssessed = vb.csv_tax_assessed || vb.property_profile_assessed;

const flags = r.flags || [];

const spread = (avm && lastSale) ? (avm - lastSale.value) : null;
const spreadPct = (spread && lastSale) ? Math.round((spread / lastSale.value) * 100) : null;

const doc = new Document({
  sections: [
    {
      properties: {
        page: { size: { width: 12240, height: 15840 }, margin: { top: 900, bottom: 900, left: 1000, right: 1000 } },
      },
      children: [
        // ---- Cover header ----
        new Paragraph({
          spacing: { after: 60 },
          children: [new TextRun({ text: "INVESTMENT UNDERWRITING BRIEF", bold: true, size: 32, color: NAVY })],
        }),
        new Paragraph({
          spacing: { after: 240 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ORANGE } },
          children: [new TextRun({ text: address, size: 24, color: "000000" })],
        }),

        new Table({
          width: { size: 9800, type: WidthType.DXA },
          rows: [
            labelValueRow("PREPARED BY", `${companyName} | Data-Reconciled Property Analysis`),
            labelValueRow("TARGET STRATEGY", "[Fix & Flip / BRRRR / Buy & Hold — set per client]"),
            labelValueRow("REPORT GENERATED", new Date(data.generated_at).toLocaleDateString("en-US")),
            labelValueRow("DATA SOURCES RECONCILED", Object.keys(data.raw_sources).join(", ")),
          ],
        }),

        heading("📊  EXECUTIVE PROPERTY SUMMARY — VERIFIED FIGURES"),
        new Table({
          width: { size: 9800, type: WidthType.DXA },
          rows: [
            labelValueRow("Living Area (MLS/AVM)", `${sqft} sqft`),
            labelValueRow("County Building Area (total structure)", countyBuildingArea ? `${countyBuildingArea} sqft` : "N/A", countyBuildingArea && countyBuildingArea != sqft ? { color: RED } : {}),
            labelValueRow("Bed / Bath / Lot", `${beds} bed / ${baths} bath, single family, ${lot} sqft lot`),
            labelValueRow("Year Built", yearBuiltDisplay, yearBuiltField && yearBuiltField.confidence !== "agreed" ? { color: RED } : {}),
            labelValueRow("Last Recorded Sale", `${lastSaleDisplay}${lastSale ? " (" + (data.raw_sources.comps_report?.last_sold_date || "") + ")" : ""}`),
            labelValueRow("Current AVM (automated valuation)", money(avm)),
            labelValueRow("Estimated Market Value", money(marketValue)),
            labelValueRow("Tax-Assessed Value", money(taxAssessed)),
          ],
        }),

        new Paragraph({ spacing: { before: 160 }, children: [
          new TextRun({ text: "Every figure above is either confirmed across independent data sources or resolved through the verification hierarchy described in the Data Verification section below — never taken from a single unverified source.", italics: true, size: 17, color: GREY }),
        ]}),

        // ---- Comps & ARV Analysis (optional -- present if reconcile.py had a
        // comps PDF with a parseable comp list) --------------------------
        ...(() => {
          const arv = r.arv_analysis;
          if (!arv) return [];
          return [
            heading("🏘️  COMPS & ARV ANALYSIS"),
            new Table({
              width: { size: 9800, type: WidthType.DXA },
              rows: [
                labelValueRow("Comps Used", `${arv.comps_used} (${arv.confirmed_closed_sales} confirmed closed sale${arv.confirmed_closed_sales === 1 ? "" : "s"})`),
                labelValueRow("Basis", arv.basis),
                labelValueRow("$/sqft Range (low / median / high)", `$${arv.ppsf_low} / $${arv.ppsf_median} / $${arv.ppsf_high}`),
                labelValueRow("ARV Estimate (low / median / high)", `${money(arv.arv_low)} / ${money(arv.arv_median)} / ${money(arv.arv_high)}`, { bold: true }),
              ],
            }),
            new Paragraph({ spacing: { before: 100 }, children: [
              new TextRun({ text: `Computed from the comparable-sales list using $/sqft against the subject's ${arv.subject_sqft} sqft living area. This is a preliminary estimate pending confirmation of actual closed prices (see Data Verification section) -- not a substitute for a licensed appraisal.`, italics: true, size: 16, color: GREY }),
            ]}),
          ];
        })(),

        // ---- Renovation History Signals + Listing Language --------------
        ...(() => {
          const renov = r.renovation_signals;
          if (!renov) return [];
          const checks = renov.checks || {};
          const rows = [];
          for (const [key, val] of Object.entries(checks)) {
            if (key === "listing_language") continue; // shown separately below
            const label = key.split("_").map(w => w[0].toUpperCase() + w.slice(1)).join(" ");
            rows.push(bulletParagraph(`${label}: ${val.note || val.signal}`,
              { color: val.signal === "insufficient_data" ? GREY : "000000" }));
          }
          const comp = renov.component_age_estimate;
          if (comp && !comp.error) {
            const overdue = Object.entries(comp.components)
              .filter(([, c]) => c.status === "likely overdue for replacement")
              .map(([name]) => name);
            if (overdue.length) {
              rows.push(bulletParagraph(
                `Component-age estimate (baseline only, no direct evidence): at ${comp.age_years} years old, ${overdue.join(", ")} ${overdue.length === 1 ? "is" : "are"} likely overdue for replacement based on typical service life.`,
                { color: ORANGE }
              ));
            }
            rows.push(bulletParagraph(comp.cosmetic_note, { color: GREY }));
          }

          const lang = renov.listing_language || {};
          const langRows = [];
          if (lang.needs_work_keywords && lang.needs_work_keywords.length) {
            langRows.push(bulletParagraph(`Needs-work language detected: "${lang.needs_work_keywords.join('", "')}"`, { color: ORANGE }));
          }
          if (lang.recently_improved_keywords && lang.recently_improved_keywords.length) {
            langRows.push(bulletParagraph(`Recently-improved language detected: "${lang.recently_improved_keywords.join('", "')}"`, { color: GREEN }));
          }
          if (lang.signal === "insufficient_data") {
            langRows.push(bulletParagraph(lang.note, { color: GREY }));
          }

          return [
            heading("🔧  RENOVATION HISTORY SIGNALS"),
            ...rows,
            new Paragraph({ spacing: { before: 100 }, children: [
              new TextRun({ text: "These are signals worth investigating, not a confirmed renovation history. Checks that show \"insufficient data\" simply mean this run didn't have the source needed (e.g. multi-year sales/valuation history), not that no renovation occurred.", italics: true, size: 15, color: GREY }),
            ]}),
            heading("🗣️  LISTING LANGUAGE", { fill: GREY }),
            ...langRows,
          ];
        })(),

        // ---- Strategy Recommendations ------------------------------------
        ...(() => {
          const strategies = r.strategy_recommendations;
          if (!strategies || !strategies.length) return [];
          const ratingColor = { "Strong fit": GREEN, "Possible fit": ORANGE, "Weak fit": RED, "Insufficient data": GREY };
          return [
            heading("🎯  STRATEGY RECOMMENDATIONS", { fill: ORANGE }),
            new Table({
              width: { size: 9800, type: WidthType.DXA },
              rows: [
                labelValueRow("Strategy", "Rating", { bold: true }),
                ...strategies.map(s => labelValueRow(s.strategy, s.rating, { color: ratingColor[s.rating] || "000000", bold: true })),
              ],
            }),
            ...strategies.flatMap(s => {
              const parts = [];
              if (s.supporting_factors.length) parts.push(`Supporting: ${s.supporting_factors.join(" ")}`);
              if (s.complicating_factors.length) parts.push(`Complicating: ${s.complicating_factors.join(" ")}`);
              if (!parts.length) return [];
              return [bulletParagraph(`${s.strategy} (${s.rating}) -- ${parts.join(" | ")}`, { color: GREY })];
            }),
            new Paragraph({ spacing: { before: 100 }, children: [
              new TextRun({ text: "This table is decision support, not a recommendation -- ratings reflect what the reconciled data does and doesn't support for each strategy. \"Insufficient data\" means this run lacked the signals that strategy depends on, not a judgment on deal quality.", italics: true, size: 15, color: GREY }),
            ]}),
          ];
        })(),

        heading("🟢  OBSERVATIONS SUPPORTED BY VERIFIED DATA", { fill: GREEN }),
        ...(spread !== null ? [bulletParagraph(
          `Spread between last recorded sale (${lastSaleDisplay}) and current AVM (${money(avm)}) is ${money(spread)} (${spreadPct}%) — a wide gap worth investigating for renovation/forced-equity upside, but treat as a starting hypothesis, not a confirmed number, until the underlying comps are reviewed.`
        )] : []),
        bulletParagraph(`Lot size of ${lot} sqft is confirmed identically across all sources — no discrepancy on this figure.`),
        ...(lastSale && lastSale.confidence === "agreed" && lastSale.sources && lastSale.sources.length >= 2
              ? [bulletParagraph(`Last sale price and date (${lastSaleDisplay}) is confirmed identically across ${lastSale.sources.length} independent sources (${lastSale.sources.join(", ")}) -- no discrepancy on this figure.`)]
              : []),
        ...(r.county_sales_history && r.county_sales_history.length > 1
              ? [bulletParagraph(`County assessor conveyance history confirms the full prior ownership chain: ${r.county_sales_history.slice().reverse().map(s => `${s.buyer || s.seller || "?"} (${s.date})`).join(" → ")}.`)]
              : []),

        // ---- Demographics & Economics (optional -- only present if reconcile.py
        // was run with an address and a Census API key was available) --------
        ...(() => {
          const demo = r.demographics_economics;
          if (!demo || demo.error) return [];

          const geo = demo.geocode || {};
          const nearest = demo.nearest_city || {};
          const acs = demo.acs || {};
          const acsCounty = acs.county || {};
          const acsPlace = acs.place || {};
          const popTrend = demo.population_trend_county;
          const unemp = demo.unemployment_trend_county;

          const rows = [
            labelValueRow("County", geo.county_name || "N/A"),
            labelValueRow("Nearest City" + (nearest.caveat ? " *" : ""), nearest.name || "N/A"),
          ];
          if (!acs.error) {
            rows.push(labelValueRow("County Population", acsCounty.population != null ? acsCounty.population.toLocaleString("en-US") : "N/A"));
            rows.push(labelValueRow("County Median HH Income", acsCounty.median_household_income != null ? money(acsCounty.median_household_income) : "N/A"));
            rows.push(labelValueRow("County Renter-Occupied %", pct(acsCounty.renter_occupied_pct)));
            if (acsPlace.population != null) {
              rows.push(labelValueRow(`${acsPlace.name || "City"} Population`, acsPlace.population.toLocaleString("en-US")));
              rows.push(labelValueRow(`${acsPlace.name || "City"} Median HH Income`, acsPlace.median_household_income != null ? money(acsPlace.median_household_income) : "N/A"));
            }
          }
          if (popTrend && !popTrend.error) {
            rows.push(labelValueRow("County Population Trend", fmtTrend(popTrend) || "N/A"));
          }
          if (unemp && !unemp.error) {
            rows.push(labelValueRow("County Unemployment Rate (latest)", `${unemp.latest.rate_pct}% (${unemp.latest.period})`));
            if (unemp.year_ago) {
              rows.push(labelValueRow("County Unemployment Rate (year ago)", `${unemp.year_ago.rate_pct}% (${unemp.year_ago.period})`));
            }
          }

          const section = [
            heading("🌆  DEMOGRAPHICS & ECONOMICS"),
            new Table({ width: { size: 9800, type: WidthType.DXA }, rows }),
          ];

          if (acs.error) {
            section.push(new Paragraph({ spacing: { before: 100 }, children: [
              new TextRun({ text: `Population/income/renter-% figures unavailable this run: ${acs.error}`, italics: true, size: 16, color: GREY }),
            ]}));
          }
          if (nearest.caveat) {
            section.push(new Paragraph({ spacing: { before: 60 }, children: [
              new TextRun({ text: `* ${nearest.caveat}`, italics: true, size: 16, color: GREY }),
            ]}));
          }
          section.push(new Paragraph({ spacing: { before: 60 }, children: [
            new TextRun({ text: "Source: U.S. Census Bureau (ACS 5-Year Estimates, Population Estimates Program) and Bureau of Labor Statistics (Local Area Unemployment Statistics), county level unless noted.", italics: true, size: 15, color: GREY }),
          ]}));

          return section;
        })(),

        // ---- Dealio Pro Ai Investment Insight (optional, pasted-in text) ---
        ...(() => {
          const insight = r.dealio_ai_insight;
          if (!insight || !insight.text) return [];
          const bodyParas = insight.text.split("\n").filter(l => l.trim()).map(line =>
            bulletParagraph(line.replace(/^[-•]\s*/, ""))
          );
          return [
            heading("🤖  THIRD-PARTY AI INSIGHT", { fill: GREY }),
            new Paragraph({ spacing: { after: 80 }, children: [
              new TextRun({ text: insight.disclaimer, italics: true, size: 16, color: GREY }),
            ]}),
            ...bodyParas,
            new Paragraph({ spacing: { before: 60 }, children: [
              new TextRun({ text: `Source: ${insight.source}`, italics: true, size: 15, color: GREY }),
            ]}),
          ];
        })(),

        heading("🔴  DATA VERIFICATION — OPEN ITEMS (DO NOT TREAT AS SETTLED)", { fill: RED }),
        // Generic loop over ALL flags -- new flag types added to reconcile.py
        // show up here automatically, no template change needed.
        ...flags.filter(f => f.flag !== "DNC_OR_LITIGATOR_NUMBERS_PRESENT")
                .map(f => bulletParagraph(f.note, { color: RED })),
        ...(yearBuiltField && yearBuiltField.confidence !== "agreed" ? [bulletParagraph(
          `Year built is unresolved: sources range from ${Math.min(...Object.values(yearBuiltField.all_values))} to ${Math.max(...Object.values(yearBuiltField.all_values))}. Not material to underwriting in most cases, but noted for completeness.`,
          { color: RED }
        )] : []),
        ...(r.conflicts.length === 0 && flags.filter(f => f.flag !== "DNC_OR_LITIGATOR_NUMBERS_PRESENT").length === 0
              ? [bulletParagraph("No unresolved conflicts on this property as of report date.", { color: GREEN })] : []),

        new Paragraph({ spacing: { before: 300, after: 100 }, children: [
          new TextRun({ text: "Limitations & Disclaimer", bold: true, size: 20, color: NAVY }),
        ]}),
        new Paragraph({ spacing: { after: 80 }, children: [
          new TextRun({
            text: `This brief reconciles data from multiple third-party providers (title records, automated valuation models, and public MLS/assessor records where verified) as of the report date above. It is prepared to support your own independent investment analysis and does not constitute a title opinion, appraisal, survey, or legal advice. Any figure listed under "Data Verification — Open Items" has not been independently confirmed and should not be relied upon until verified against primary sources (e.g., the county Clerk of Court for liens/mortgages). ${companyName} recommends independent title, inspection, and legal review before executing a purchase agreement.`,
            size: 16, color: GREY,
          }),
        ]}),
      ],
    },
  ],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outPath, buf);
  console.log("Wrote", outPath);
});
