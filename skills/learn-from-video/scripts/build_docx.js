#!/usr/bin/env node
/**
 * build_docx.js — render a document spec (JSON) into a .docx.
 *
 * WHY THIS EXISTS
 * Previously the docx-js code was hand-written on every run. That meant the
 * gotchas (ImageRun needs `type`, ShadingType.SOLID renders black, tables need
 * width in two places, the TableOfContents widget renders empty outside Word)
 * had to be remembered every time, and any mistake shipped silently. It also
 * meant the output layer could not be tested.
 *
 * Now the model produces content as JSON and this renders it. The gotchas live
 * here once, correctly.
 *
 *   node build_docx.js spec.json
 *   node build_docx.js spec.json --out other.docx
 *
 * SPEC
 * {
 *   "output": "C:/path/out.docx",
 *   "title": "...", "subtitle": "...",
 *   "meta": [["Instructor","..."], ["Duration","39:03"]],
 *   "footer": "Notes generated from video for personal learning use",
 *   "toc": [["1","Executive Summary",3], ...],
 *   "sections": [
 *     { "heading": "1. Executive Summary", "pageBreakBefore": true,
 *       "blocks": [ ...see BLOCK TYPES... ] }
 *   ]
 * }
 *
 * BLOCK TYPES
 *   {"type":"h2"|"h3","text":"..."}
 *   {"type":"p","text":"...","italic":false,"bold":false}
 *   {"type":"ts","time":"10:12","text":"..."}         timestamped paragraph
 *   {"type":"bullets","items":["...","..."],"level":0}
 *   {"type":"image","path":"...","caption":"...","width":560,"height":315}
 *   {"type":"table","headers":[...],"rows":[[...]],"widths":[...]}
 *   {"type":"callout","style":"key"|"warn"|"screen","title":"...","body":[...]}
 *   {"type":"code","language":"js","text":"..."}
 *   {"type":"spacer"} | {"type":"pagebreak"}
 */
'use strict';

const fs = require('fs');
const path = require('path');

/**
 * Resolve `docx` from the CALLER's directory, not this script's.
 *
 * The skill is installed under ~/.claude/skills/... but `npm install docx`
 * happens in the user's working directory. Node resolves modules relative to
 * the script, so a plain require('docx') fails with MODULE_NOT_FOUND even
 * though docx is installed exactly where the instructions said to install it.
 */
function loadDocx() {
  const tried = [];
  const candidates = [
    null,                                             // normal resolution
    path.join(process.cwd(), 'node_modules', 'docx'), // caller's cwd
    ...(process.env.NODE_PATH ? [path.join(process.env.NODE_PATH, 'docx')] : []),
  ];
  for (const c of candidates) {
    try {
      return c ? require(c) : require('docx');
    } catch (e) {
      tried.push(c || 'docx');
    }
  }
  console.error(
    'ERROR: the `docx` package could not be found.\n' +
    `  Looked in: ${tried.join(', ')}\n` +
    '  Fix: run `npm install docx` in your working directory, then re-run from that directory.'
  );
  process.exit(2);
}

const {
  Document, Packer, Paragraph, TextRun, ImageRun, AlignmentType, HeadingLevel,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, LevelFormat,
  Header, Footer, PageNumber, convertInchesToTwip, PageBreak,
} = loadDocx();

const C = { orange: 'E8590C', grey: '666666', dark: '1A1A1A', blue: '1B5E9E', red: 'B02A2A', code: '0B3D2E' };
const STYLE = { key: C.orange, warn: C.red, screen: C.blue };
const CONTENT_W = 9360; // twips inside 0.9in margins on US Letter

const warnings = [];

const p = (text, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 120, line: 300 }, alignment: o.align,
  children: [new TextRun({ text: String(text ?? ''), size: o.size ?? 22, bold: !!o.bold, italics: !!o.italic, color: o.color || C.dark })],
});

const heading = (text, level) => new Paragraph({
  heading: level === 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3,
  spacing: { before: level === 1 ? 400 : level === 2 ? 300 : 220, after: level === 1 ? 200 : 130 },
  children: [new TextRun({ text, bold: true, size: level === 1 ? 32 : level === 2 ? 26 : 23,
    color: level === 1 ? C.orange : level === 2 ? C.dark : C.blue })],
});

function imageBlock(b) {
  const file = b.path;
  if (!file || !fs.existsSync(file)) {
    warnings.push(`missing image: ${file}`);
    return [p(`[screenshot missing: ${path.basename(file || 'unknown')}]`, { italic: true, color: C.red })];
  }
  const ext = path.extname(file).toLowerCase();
  // REQUIRED by docx-js — omitting `type` throws at render time.
  const type = ext === '.png' ? 'png' : ext === '.gif' ? 'gif' : ext === '.bmp' ? 'bmp' : 'jpg';
  const w = Math.min(b.width || 560, 560);           // fit 1in margins
  const h = b.height || Math.round(w * 9 / 16);
  const out = [new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 160, after: 60 },
    children: [new ImageRun({ data: fs.readFileSync(file), transformation: { width: w, height: h }, type })],
  })];
  if (b.caption) {
    out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
      children: [new TextRun({ text: b.caption, size: 18, italics: true, color: C.grey })] }));
  }
  return out;
}

function tableBlock(b) {
  const headers = b.headers || [];
  const cols = Math.max(headers.length, ...(b.rows || [[]]).map(r => r.length), 1);
  let widths = b.widths && b.widths.length === cols ? b.widths.slice() : null;
  if (!widths) widths = Array(cols).fill(Math.floor(CONTENT_W / cols));
  const total = widths.reduce((a, x) => a + x, 0);
  if (total > CONTENT_W) {                            // never overflow the page
    const k = CONTENT_W / total;
    widths = widths.map(w => Math.floor(w * k));
  }
  const cell = (txt, head, w) => new TableCell({
    width: { size: w, type: WidthType.DXA },          // DXA, not PERCENTAGE
    shading: { type: ShadingType.CLEAR, fill: head ? C.orange : 'FFFFFF' }, // CLEAR, not SOLID
    margins: { top: 90, bottom: 90, left: 130, right: 130 },
    children: [new Paragraph({ children: [new TextRun({ text: String(txt ?? ''), bold: head, size: 20, color: head ? 'FFFFFF' : C.dark })] })],
  });
  const rows = [];
  if (headers.length) rows.push(new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, true, widths[i])) }));
  for (const r of (b.rows || [])) {
    const cells = [];
    for (let i = 0; i < cols; i++) cells.push(cell(r[i], false, widths[i]));
    rows.push(new TableRow({ children: cells }));
  }
  return new Table({
    width: { size: widths.reduce((a, x) => a + x, 0), type: WidthType.DXA },
    columnWidths: widths,                              // BOTH required
    borders: {
      top: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' },
      left: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' },
      right: { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: 'DDDDDD' },
      insideVertical: { style: BorderStyle.SINGLE, size: 1, color: 'DDDDDD' },
    },
    rows,
  });
}

function calloutBlock(b) {
  const color = STYLE[b.style] || C.orange;
  const body = (b.body || []).map(t => new Paragraph({ spacing: { after: 50 },
    children: [new TextRun({ text: String(t), size: 21, color: C.dark })] }));
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color },
      bottom: { style: BorderStyle.SINGLE, size: 2, color },
      left: { style: BorderStyle.SINGLE, size: 18, color },   // accent bar
      right: { style: BorderStyle.SINGLE, size: 2, color },
    },
    rows: [new TableRow({ children: [new TableCell({
      width: { size: CONTENT_W, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: 'F7F7F7' },
      margins: { top: 140, bottom: 140, left: 180, right: 180 },
      children: [
        ...(b.title ? [new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: b.title, bold: true, size: 22, color })] })] : []),
        ...body,
      ],
    })] })],
  });
}

function codeBlock(b) {
  const lines = String(b.text || '').split('\n');
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 1, color: 'DDDDDD' },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: 'DDDDDD' },
      left: { style: BorderStyle.SINGLE, size: 12, color: C.code },
      right: { style: BorderStyle.SINGLE, size: 1, color: 'DDDDDD' },
    },
    rows: [new TableRow({ children: [new TableCell({
      width: { size: CONTENT_W, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: 'F4F6F5' },
      margins: { top: 120, bottom: 120, left: 160, right: 160 },
      children: [
        ...(b.language ? [new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: b.language, size: 16, bold: true, color: C.grey })] })] : []),
        ...lines.map(l => new Paragraph({ spacing: { after: 0, line: 260 },
          children: [new TextRun({ text: l || ' ', font: 'Consolas', size: 18, color: C.dark })] })),
      ],
    })] })],
  });
}

function renderBlock(b) {
  switch (b.type) {
    case 'h2': return [heading(b.text, 2)];
    case 'h3': return [heading(b.text, 3)];
    case 'p': return [p(b.text, { bold: b.bold, italic: b.italic })];
    case 'ts': return [new Paragraph({ spacing: { after: 120, line: 300 }, children: [
      new TextRun({ text: `[${b.time}] `, size: 20, bold: true, color: C.orange }),
      new TextRun({ text: String(b.text ?? ''), size: 22, color: C.dark })] })];
    case 'bullets': return (b.items || []).map(t => new Paragraph({
      bullet: { level: b.level || 0 }, spacing: { after: 70, line: 290 },
      children: [new TextRun({ text: String(t), size: 22, color: C.dark })] }));
    case 'image': return imageBlock(b);
    case 'table': return [tableBlock(b)];
    case 'callout': return [calloutBlock(b)];
    case 'code': case 'mermaid': return [codeBlock(b.type === 'mermaid' ? { ...b, language: 'mermaid' } : b)];
    case 'spacer': return [new Paragraph({ spacing: { after: 200 }, children: [new TextRun('')] })];
    case 'pagebreak': return [new Paragraph({ children: [new PageBreak()] })];
    default:
      warnings.push(`unknown block type: ${b.type}`);
      return [];
  }
}

function build(spec) {
  const kids = [];

  // ---- cover
  kids.push(new Paragraph({ spacing: { before: 1400, after: 120 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: spec.title || 'Untitled', bold: true, size: 46, color: C.orange })] }));
  if (spec.subtitle) {
    kids.push(new Paragraph({ spacing: { after: 400 }, alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: spec.subtitle, size: 26, color: C.grey })] }));
  }
  for (const [k, v] of (spec.meta || [])) {
    kids.push(new Paragraph({ spacing: { after: 90 }, alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: `${k}: `, size: 20, bold: true, color: C.grey }),
                 new TextRun({ text: String(v), size: 20, color: C.dark })] }));
  }
  kids.push(new Paragraph({ children: [new PageBreak()] }));

  // ---- manual TOC (the widget renders empty outside Word)
  if (spec.toc && spec.toc.length) {
    kids.push(heading('Table of Contents', 1), renderBlock({ type: 'spacer' })[0]);
    for (const [n, t, pg] of spec.toc) {
      const dots = '.'.repeat(Math.max(3, 62 - String(t).length));
      kids.push(new Paragraph({ spacing: { after: 80 }, children: [
        new TextRun({ text: `${n}. ${t}`, size: 22, color: C.dark }),
        new TextRun({ text: `  ${dots}  `, size: 22, color: 'AAAAAA' }),
        new TextRun({ text: String(pg), size: 22, color: C.dark })] }));
    }
    kids.push(new Paragraph({ children: [new PageBreak()] }));
  }

  // ---- sections
  for (const s of (spec.sections || [])) {
    if (s.pageBreakBefore) kids.push(new Paragraph({ children: [new PageBreak()] }));
    if (s.heading) kids.push(heading(s.heading, 1));
    for (const b of (s.blocks || [])) kids.push(...renderBlock(b));
  }

  return new Document({
    creator: 'learnFromVideo', title: spec.title || 'Notes',
    description: spec.description || 'Learning notes generated from video',
    numbering: { config: [{ reference: 'lfv', levels: [
      { level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 460, hanging: 240 } } } },
      { level: 1, format: LevelFormat.BULLET, text: '\u25E6', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 900, hanging: 240 } } } }] }] },
    sections: [{
      properties: { page: { margin: {
        top: convertInchesToTwip(0.9), bottom: convertInchesToTwip(0.9),
        left: convertInchesToTwip(0.9), right: convertInchesToTwip(0.9) } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: spec.header || `${spec.title || ''}  |  learnFromVideo Notes`, size: 16, color: C.grey })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: (spec.footer || 'learnFromVideo Notes') + '  |  Page ', size: 16, color: C.grey }),
                   new TextRun({ children: [PageNumber.CURRENT], size: 16, color: C.grey })] })] }) },
      children: kids,
    }],
  });
}

async function main() {
  const args = process.argv.slice(2);
  if (!args.length) {
    console.error('usage: node build_docx.js <spec.json> [--out FILE]');
    process.exit(2);
  }
  const specPath = args[0];
  const outIdx = args.indexOf('--out');
  let spec;
  try {
    spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  } catch (e) {
    console.error(`ERROR: cannot read spec (${e.message})`);
    process.exit(2);
  }
  const out = outIdx >= 0 ? args[outIdx + 1] : spec.output;
  if (!out) { console.error('ERROR: no output path (spec.output or --out)'); process.exit(2); }

  const blocks = (spec.sections || []).reduce((n, s) => n + (s.blocks || []).length, 0);
  const images = (spec.sections || []).reduce((n, s) => n + (s.blocks || []).filter(b => b.type === 'image').length, 0);

  let buf;
  try {
    buf = await Packer.toBuffer(build(spec));
  } catch (e) {
    console.error(`ERROR: render failed (${e.message})`);
    process.exit(1);
  }
  fs.mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
  fs.writeFileSync(out, buf);

  console.log(JSON.stringify({
    ok: true, output: out,
    size_mb: +(buf.length / 1048576).toFixed(2),
    sections: (spec.sections || []).length,
    blocks, images, warnings,
  }, null, 2));
  if (warnings.length) console.error(`[build_docx] ${warnings.length} warning(s)`);
}

main();
