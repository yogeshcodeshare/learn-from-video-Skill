# Report Structure Reference — learnFromVideo

This document defines the formatting guidelines for the Word document output. Use `docx-js` (`npm install docx`) to generate the .docx file.

**IMPORTANT**: This file covers FORMATTING and docx-js code patterns. The actual STRUCTURE of the report is adaptive — it follows the video's natural flow, not a rigid template. See SKILL.md for the content strategy.

## Document Setup

```javascript
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, LevelFormat, ExternalHyperlink,
        TableOfContents, HeadingLevel, BorderStyle, WidthType, ShadingType,
        PageBreak, PageNumber, ImageRun } = require('docx');
const fs = require('fs');
```

### Page Configuration
- Page size: US Letter (12240 x 15840 DXA)
- Margins: 1 inch all sides (1440 DXA)
- Content width: 9360 DXA

### Color Palette
- Primary heading: `"1B4F72"` (deep blue)
- Section headings: `"2E75B6"` (medium blue)
- Accent/highlight: `"E8F4FD"` (light blue background for callout boxes)
- Code background: `"F5F5F5"` (light gray)
- Timestamp color: `"666666"` (gray)
- Body text: `"333333"` (dark gray)
- Link color: `"2E75B6"`
- Note text: `"999999"` (light gray)

### Typography
- Body: Arial, 11pt (size: 22)
- Headings: Arial Bold
  - H1: 18pt (size: 36), color: `"1B4F72"`
  - H2: 15pt (size: 30), color: `"2E75B6"`
  - H3: 13pt (size: 26), color: `"2E75B6"`
- Code: Courier New, 10pt (size: 20)
- Timestamps: Arial Italic, 9pt, color: `"666666"`
- Footnotes/attribution: Arial, 8pt, color: `"999999"`

## Fixed Structural Elements

These elements appear in every report, in this order:

### 1. Cover Page
- Report title — centered, 24pt bold, primary color
- Subtitle — centered, 14pt, medium blue
- Channel, date, duration
- Video URL(s) as clickable hyperlinks
- Topic tags
- "learnFromVideo — Comprehensive Learning Report"
- Page break after cover

### 2. Table of Contents (MANUAL)

**DO NOT use the docx-js `TableOfContents` widget.** It creates an empty placeholder that only populates in Microsoft Word when manually updated. Instead, create a MANUAL table of contents:

```javascript
// Manual TOC - list each section heading
const tocEntries = [
  { title: "Executive Summary", page: "3" },
  { title: "Part 1: The PSB System", page: "4" },
  { title: "Part 2: 52 Tips - Beginner to Master", page: "12" },
  // ... etc
];

const tocParagraphs = [
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: "Table of Contents", bold: true, size: 36, color: "1B4F72", font: "Arial" })],
    spacing: { after: 300 },
  }),
  ...tocEntries.map(entry => new Paragraph({
    spacing: { before: 60, after: 60 },
    children: [
      new TextRun({ text: entry.title, size: 24, font: "Arial", color: "333333" }),
    ],
    indent: { left: 360 },
  })),
  new Paragraph({ children: [new PageBreak()] }),
];
```

Note: Page numbers in a manual TOC are approximate since docx-js doesn't know final pagination. You can omit page numbers and just list the sections, or use dots/dashes as visual separators.

### 3. Video Sources Table (for multi-video only)
| # | Video Title | Channel | Duration | URL |
|---|-------------|---------|----------|-----|

### 4. Executive Summary
- 3-5 key takeaways as bullet points (use LevelFormat.BULLET)
- What the video teaches, target audience, prerequisites
- Difficulty level
- Half a page maximum

### 5. [ADAPTIVE CORE CONTENT — structure driven by the video]

### 6. Quick Reference Tables
- Commands, tools, key facts for quick scanning
- Table with colored header row

### 7. Source Videos & Resources
- Video URLs as clickable hyperlinks
- Tools and resources mentioned
- Attribution note

## Inline Formatting Elements

These formatting elements are used WITHIN the adaptive core content sections. They appear wherever relevant — NOT in separate chapters.

### Embedded Screenshot (Inline)
Use when embedding an actual screenshot from the video:

```javascript
// Read the screenshot image
const imageBuffer = fs.readFileSync('/tmp/lfv-screenshots/frame_0125.jpg');

// Embed the screenshot
new Paragraph({
  children: [new ImageRun({
    data: imageBuffer,
    transformation: { width: 560, height: 315 },  // 16:9 aspect ratio, fits in margins
    type: 'jpg',  // REQUIRED - must specify 'jpg' or 'png'
  })],
  alignment: AlignmentType.CENTER,
  spacing: { before: 120, after: 60 },
}),
// Caption below the screenshot
new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
  children: [
    new TextRun({ text: "Screenshot at [12:34]: ", bold: true, italics: true, size: 18, color: "666666", font: "Arial" }),
    new TextRun({ text: "The presenter shows the system architecture diagram", italics: true, size: 18, color: "666666", font: "Arial" }),
  ],
}),
```

**IMPORTANT ImageRun notes:**
- The `type` parameter is REQUIRED — without it, the image will not render
- Use `'jpg'` for JPEG files, `'png'` for PNG files
- Read the file as a Buffer: `fs.readFileSync(path)`
- Max width ~560px to fit within 1-inch margins on US Letter
- For 16:9 video frames: width: 560, height: 315
- For 4:3 frames: width: 560, height: 420
- Always add a caption paragraph below with timestamp and description

### Code Blocks (Inline)
Use when code is shown or discussed at any point in the video:
```javascript
new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [9360],
  rows: [new TableRow({ children: [new TableCell({
    shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
    borders: { top: border, bottom: border, left: border, right: border },
    margins: { top: 100, bottom: 100, left: 200, right: 200 },
    width: { size: 9360, type: WidthType.DXA },
    children: [
      // Optional language label
      new Paragraph({ children: [new TextRun({ text: "// JavaScript", font: "Courier New", size: 18, color: "999999" })] }),
      // Each code line as a separate Paragraph in Courier New
      new Paragraph({ children: [new TextRun({ text: "const app = express();", font: "Courier New", size: 20 })] }),
    ]
  })]})],
})
```

### Code Block with Video Source Markers
When code is captured from a screenshot and completed:
```javascript
new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [9360],
  rows: [new TableRow({ children: [new TableCell({
    shading: { fill: "F5F5F5", type: ShadingType.CLEAR },
    borders: { top: border, bottom: border, left: border, right: border },
    margins: { top: 100, bottom: 100, left: 200, right: 200 },
    width: { size: 9360, type: WidthType.DXA },
    children: [
      new Paragraph({ children: [new TextRun({ text: "// JavaScript — CLAUDE.md configuration", font: "Courier New", size: 18, color: "999999" })] }),
      // FROM VIDEO marker
      new Paragraph({ children: [new TextRun({ text: "// === FROM VIDEO [11:36] ===", font: "Courier New", size: 18, color: "2E75B6", bold: true })] }),
      new Paragraph({ children: [new TextRun({ text: 'const config = {', font: "Courier New", size: 20 })] }),
      new Paragraph({ children: [new TextRun({ text: '  model: "claude-sonnet-4-20250514",', font: "Courier New", size: 20 })] }),
      new Paragraph({ children: [new TextRun({ text: '};', font: "Courier New", size: 20 })] }),
      // ADDED FOR COMPLETENESS marker
      new Paragraph({ children: [new TextRun({ text: "// === ADDED FOR COMPLETENESS ===", font: "Courier New", size: 18, color: "4CAF50", bold: true })] }),
      new Paragraph({ children: [new TextRun({ text: 'import { Agent } from "./agent";', font: "Courier New", size: 20 })] }),
    ]
  })]})],
})
```

### Visual Callout Box — On-Screen Content (Inline)
Use when describing what was captured from a screenshot at a specific timestamp:
```javascript
new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [9360],
  rows: [new TableRow({ children: [new TableCell({
    shading: { fill: "E8F4FD", type: ShadingType.CLEAR },
    borders: {
      top: { style: BorderStyle.NONE },
      bottom: { style: BorderStyle.NONE },
      right: { style: BorderStyle.NONE },
      left: { style: BorderStyle.SINGLE, size: 8, color: "2E75B6" }
    },
    margins: { top: 80, bottom: 80, left: 200, right: 120 },
    width: { size: 9360, type: WidthType.DXA },
    children: [
      new Paragraph({ children: [
        new TextRun({ text: "On Screen [12:34]: ", bold: true, size: 20, color: "2E75B6" }),
      ]}),
      new Paragraph({ children: [
        new TextRun({ text: "The presenter shows a slide titled 'System Architecture' with three boxes labeled...", size: 22 }),
      ]}),
    ]
  })]})],
})
```

### Mermaid Diagram Block (Inline)
Use when recreating a diagram that was shown or described:
```javascript
new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [9360],
  rows: [new TableRow({ children: [new TableCell({
    shading: { fill: "F8F8F8", type: ShadingType.CLEAR },
    borders: { top: border, bottom: border, left: border, right: border },
    margins: { top: 100, bottom: 100, left: 200, right: 200 },
    width: { size: 9360, type: WidthType.DXA },
    children: [
      new Paragraph({ children: [
        new TextRun({ text: "Diagram: System Architecture", font: "Courier New", size: 18, color: "999999", italics: true }),
      ]}),
      new Paragraph({ children: [new TextRun({ text: "graph LR", font: "Courier New", size: 20 })] }),
      new Paragraph({ children: [new TextRun({ text: "    Client --> API_Gateway", font: "Courier New", size: 20 })] }),
    ]
  })]})],
})
```

### Key Insight Callout (Inline)
Use for especially important statements:
```javascript
new Paragraph({
  spacing: { before: 120, after: 120 },
  indent: { left: 360, right: 360 },
  children: [
    new TextRun({ text: "Key Insight: ", bold: true, color: "1B4F72", size: 22, font: "Arial" }),
    new TextRun({ text: "The actual key insight text here...", italics: true, size: 22, font: "Arial" }),
  ]
})
```

### Data Tables (Inline)
Use when statistics, comparisons, or structured data is mentioned or shown:
```javascript
// Header row with colored background (D5E8F0)
// Data rows with white background
// Always use WidthType.DXA, not PERCENTAGE
// Set both columnWidths on table AND width on each cell
```

### Timestamp References
Make timestamps clickable links to the video:
```javascript
new ExternalHyperlink({
  children: [new TextRun({ text: "[12:34]", style: "Hyperlink", size: 20, font: "Arial", italics: true })],
  link: "https://youtube.com/watch?v=VIDEO_ID&t=754",
})
```

## Header and Footer

**Header:**
- Left: Video title (truncated to 50 chars if needed)
- Right: "learnFromVideo Notes"
- Bottom border line in section color

**Footer:**
- Left: "Notes generated from YouTube video for personal learning use"
- Center: Page number
- Right: Date
- Top border line in light gray

## For Multiple Videos

**Modified Cover Page:**
- Title: Topic name (not individual video title)
- "Combined Learning Notes from [N] Videos"
- List each video with title, channel, and URL

**Content Organization:**
- Merge by THEME, not by video
- Cross-reference between videos
- Use superscript-style video references where helpful (Video 1, Video 2)
- Single merged glossary, takeaways, and Q&A

## Topic Tags
Detect from transcript content and include on cover page + executive summary:
- Programming languages, frameworks, tools mentioned
- Domain (Web Dev, ML, DevOps, etc.)
- Difficulty level (Beginner / Intermediate / Advanced)
- Format: `Python | Web Development | Backend | Intermediate`

## File Naming
- Single video: `{VideoTitle}_LearnFromVideo_Notes.docx` (sanitize, max 80 chars)
- Multiple videos: `{Topic}_Combined_LearnFromVideo_Notes.docx`
- Save to user's workspace folder
