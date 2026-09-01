# Production-table style contract

## Main table

- Use one wide analyst-facing sheet with questions stacked vertically and segments expanded horizontally.
- Use a single wide left label column and compact numeric columns.
- Start every question as a self-contained block separated by two blank rows.
- Repeat, in order: pale-peach segment-family band, segment labels, dynamic question base, blue bold question, response rows, separator, and total when meaningful.
- When project indicator labels are configured, add a compact indicator-label band above the segment-family band. Derived respondent labels belong in columns as segment families, not as fake response rows.
- Use Calibri 9–11 for the main table, thin dark borders, centered numeric cells, white body cells, and minimal decoration.
- Show percentages with one decimal, means or average ranks with one decimal, NPS as an integer, and bases as integers with thousands separators.
- Never format response codes such as 1–5 as `100%–500%`. Convert codes to verified labels before applying percentage formats.
- Preserve totals above 100% for multi-select and fixed-count ranking questions.
- Place configured T2B/B2B rows immediately after Mean and before the original option rows; prefix them with `【指标】`.
- Use `-` for structurally unavailable cells and blank only for deliberate visual spacing.

## Highlighting

- In the ordinary frequency table, use pale cyan to surface cells identified as significantly high by the canonical test output; use a stronger cyan only for broader within-family advantages.
- Cyan is a scanning aid, not a replacement for the significance sheet.
- Do not invent high/low coloring from rounded displayed values.

## Significance sheet

- Use the same question blocks, column order, bases, borders, and spacing as the ordinary frequency table.
- Add within-family column letters to segment labels.
- Keep significant-high values and letters purple.
- Keep values significantly lower than every comparable member of the same family in dark yellow text with a pale-yellow fill.
- Keep non-significant cells black.

## Index and supporting sheets

- Provide an Index containing the question list for both principal sheets. Every question cell must be a working internal hyperlink to that question's blue title row. Never deliver a blue-text-only or broken-formula fallback.
- Preserve explanation, variable mapping, and data-quality sheets. Do not let these auxiliary sheets change the production-table layout of the principal sheets.
