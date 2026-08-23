// Builds Newtree_Comps_Support_Document_Template.docx
// A client-facing evidentiary backup for the ARV comps analysis cited in
// the Quick Screen / Full Model report. Only Confirmed Genuine and
// Moderate Confidence comps go here -- excluded/reclassified comps stay
// in the Internal Working Files (never shared with a client).
//
// Styling matched by hand against 4134_E_142nd_St_Fix_Flip_Analysis.docx
// (title block, Heading1 gold-underline style, body text conventions).

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell,
  WidthType, AlignmentType, BorderStyle, ShadingType, HeadingLevel,
  Header, Footer, PageNumber, PageOrientation, VerticalAlign, convertInchesToTwip
} = require("docx");

const NAVY = "19262B";
const GOLD = "D8BF77";
const BRONZE = "68521B";
const GREY = "595959";
const BODY = "222222";
const CONFIRMED_FILL = "E7F0E4"; // pale green
const MODERATE_FILL = "FBF3DD";  // pale gold/cream

const logo = fs.readFileSync("logo.png");

function goldRule() {
  return new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: GOLD, space: 4 } },
    spacing: { after: 0 },
  });
}

function heading1(text) {
  return new Paragraph({
    spacing: { before: 260, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: GOLD, space: 4 } },
    children: [
      new TextRun({ text, bold: true, color: NAVY, size: 27, font: "Calibri" }),
    ],
  });
}

function body(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 170, line: 268 },
    children: [
      new TextRun({ text, color: opts.color ?? BODY, size: opts.size ?? 20, font: "Calibri", italics: opts.italics }),
    ],
  });
}

function headerCell(text, width) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: NAVY },
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 80, right: 80 },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, bold: true, color: "FFFFFF", size: 16, font: "Calibri" })],
    })],
  });
}

function dataCell(text, width, fill) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { type: ShadingType.CLEAR, fill } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 60, bottom: 60, left: 80, right: 80 },
    children: [new Paragraph({
      children: [new TextRun({ text, color: BODY, size: 16, font: "Calibri" })],
    })],
  });
}

const COLS = [500, 1900, 1900, 900, 1200, 700, 1500, 2200]; // sums to 10800 dxa
const HEADERS = ["#", "Comp Address", "Sale History (Prior → Current)", "Buyer Type",
                  "Financing", "$/Sqft", "Tier Assigned", "Basis / Reasoning"];

function templateRow(n, fill) {
  const vals = [
    String(n),
    "[Comp Street Address, City, State ZIP]",
    "[$XXX,XXX / MM-YYYY → $XXX,XXX / MM-YYYY]",
    "[Individual / LLC / Trust]",
    "[FHA / Conventional / Cash]",
    "[$XXX]",
    "[Confirmed Genuine / Moderate Confidence]",
    "[Why this comp supports the ARV -- renovation description, listing language, transaction-pair basis]",
  ];
  return new TableRow({
    children: vals.map((v, i) => dataCell(v, COLS[i], fill)),
  });
}

const exampleRow = new TableRow({
  children: [
    dataCell("1", COLS[0], CONFIRMED_FILL),
    dataCell("16120 Harvard Ave, Cleveland, OH 44128", COLS[1], CONFIRMED_FILL),
    dataCell("$30,000 / prior → $150,000 / current", COLS[2], CONFIRMED_FILL),
    dataCell("Individual", COLS[3], CONFIRMED_FILL),
    dataCell("FHA", COLS[4], CONFIRMED_FILL),
    dataCell("$137", COLS[5], CONFIRMED_FILL),
    dataCell("Confirmed Genuine", COLS[6], CONFIRMED_FILL),
    dataCell("EXAMPLE -- verified transaction pair on same property; individual buyer + FHA financing + listing described new roof, updated electrical, refinished hardwood.", COLS[7], CONFIRMED_FILL),
  ],
});

const table = new Table({
  width: { size: 10800, type: WidthType.DXA },
  rows: [
    new TableRow({ children: HEADERS.map((h, i) => headerCell(h, COLS[i])) }),
    exampleRow,
    templateRow(2, MODERATE_FILL),
    templateRow(3, CONFIRMED_FILL),
    templateRow(4, MODERATE_FILL),
  ],
});

const doc = new Document({
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1000, bottom: 1000, left: 720, right: 720 },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({ children: [] })] }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "Page ", size: 16, color: GREY, font: "Calibri" }),
            new TextRun({ children: [PageNumber.CURRENT], size: 16, color: GREY, font: "Calibri" }),
            new TextRun({ text: " of ", size: 16, color: GREY, font: "Calibri" }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: GREY, font: "Calibri" }),
          ],
        })],
      }),
    },
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 120 },
        children: [new ImageRun({ data: logo, type: "png", transformation: { width: 130, height: 104 } })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 60 },
        children: [new TextRun({ text: "[Property Address, City, State ZIP]", italics: true, color: BRONZE, size: 22, font: "Georgia" })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 60 },
        children: [new TextRun({ text: "Prepared by Newtree Capital Resources LLC  ·  Prepared: [Month Day, Year]", color: GREY, size: 17, font: "Calibri" })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 60 },
        children: [new TextRun({ text: "Prepared For: [Client / Wholesaler Name]", bold: true, color: GREY, size: 17, font: "Calibri" })],
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 260 },
        children: [new TextRun({ text: "Comps Support Document — evidentiary backup for the ARV comparable sales analysis in the accompanying report.", italics: true, color: GREY, size: 16, font: "Calibri" })],
      }),

      heading1("ARV Comparable Sales — Support Data"),
      body("This document backs the ARV figure cited in the accompanying report with the individual comparable sales that support it. Each comp listed here was individually verified using the transaction-pair method: a real, documented price jump between two sales of the same property, checked against buyer type, financing, and the listing's own description — not just a lead-service tag taken at face value."),
      body("Only comps tagged Confirmed Genuine or Moderate Confidence appear below. Comps that were excluded (e.g. same-week wholesale double-closes, unrenovated resales) or reclassified to a different valuation tier (e.g. rental/commercial) are documented separately in this deal's Internal Working Files log — that record is internal only and is not shared with the client.", { after: 220 }),

      table,

      new Paragraph({ spacing: { before: 220, after: 60 } }),
      body("Methodology reference: see the Property Data Sourcing Guide (Rule 1 — transaction-pair verification) for the full comp validation method this document applies.", { italics: true, color: GREY, size: 16 }),
      body("Source: Newtree's comps and skip-trace platform. Pulled [Month Day, Year].", { italics: true, color: GREY, size: 16, after: 0 }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("Newtree_Comps_Support_Document_Template.docx", buf);
  console.log("written");
});
