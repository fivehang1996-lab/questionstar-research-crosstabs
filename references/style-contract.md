# Production-table style contract

## Main table

- Use one wide analyst-facing sheet with questions stacked vertically and segments expanded horizontally.
- Use a single wide left label column and compact numeric columns.
- Start every question as a self-contained block separated by two blank rows.
- Repeat, in order: muted family-color band, segment labels, dynamic question base, blue bold question, response rows, separator, and total when meaningful.
- When project indicator labels are configured, add a compact indicator-label band above the segment-family band. Derived respondent labels belong in columns as segment families, not as fake response rows.
- Use Calibri 9–11 for the main table, thin dark borders, centered numeric cells, white body cells, and minimal decoration.
- Show percentages with one decimal, means or average ranks with one decimal, NPS as an integer, and bases as integers with thousands separators.
- Never format response codes such as 1–5 as `100%–500%`. Convert codes to verified labels before applying percentage formats.
- Preserve totals above 100% for multi-select and fixed-count ranking questions.
- Place configured T2B/B2B rows immediately after Mean and before the original option rows; prefix them with `【指标】`.
- Use an em dash `—` for unavailable cells and blank only for deliberate visual spacing.

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
- Add question type and indicator category to Index, with a native return-to-Index link in every question block.
- Preserve explanation, variable mapping, and data-quality sheets. Do not let these auxiliary sheets change the production-table layout of the principal sheets.

## Version 2 readability and overview

- Freeze the first four navigation rows and the label/Total columns. Repeat per-question bases under the local header; never freeze the first question's base as if it were universal.
- Keep Total a neutral gray. Use muted peach for game experience, lavender for indicator strata, green for demographic groups and blue-gray for other families. Medium vertical rules distinguish family boundaries.
- Keep key metric rows bold and lightly separated. Arrows indicate configured desirability, not significance. Average rank is lower-is-better; do not imply that significantly higher always means better.
- Both frequency and significance sheets retain numeric cells and identical precision: 0.0%, Mean/rank 0.0, NPS integer. Append statistical letters and †/‡ through literal number formats rather than replacing numeric values with text.
- † indicates the configured small effective base; ‡ marks definition-based self-crosses. No valid sample is shown as an em dash; a measured zero remains 0.0%.
- Add `指标概览` before Index. A single family dropdown switches a compact heat table and native editable horizontal charts backed by formula links to the main table. Keep original research detail intact.
- Heat colors encode value magnitude only. Adjacent effective-n/significance columns explain uncertainty. Never reuse the frequency table's significance legend for a magnitude heatmap.
- T2B chart axes run 0–100%; NPS runs −100–100 with a visible zero origin; full scoring distributions use 100% stacked bars with a fixed low-to-high palette. Omit chart types with no source metric.
- Validate selector changes, chart cell bindings, saved chart colors, native axes, both directions of links and the exact numerical equivalence of the two main sheets. Render the finalized package, including all seven sheets and a matrix block.
