# Derived segments and box metrics

Use derived segments when answers to one question must become column groups for every question. Use box metrics when several ordered response rows must be combined inside the source question.

## Configuration

Create one project JSON. Question and option numbers must come from the delivered questionnaire, never from an outline.

```json
{
  "derived_segments": [
    {
      "family": "整体体验分层",
      "field": "指标标签_Q4整体体验",
      "question": 4,
      "source": "item_index",
      "groups": [
        {"label": "高体验（4–5分）", "values": [4, 5]},
        {"label": "非高体验（1–3分）", "values": [1, 2, 3]}
      ]
    },
    {
      "family": "推荐意愿分层",
      "field": "指标标签_Q21推荐意愿",
      "question": 21,
      "source": "item_value",
      "groups": [
        {"label": "推荐者（9–10分）", "min": 9, "max": 10},
        {"label": "非推荐者（0–8分）", "min": 0, "max": 8}
      ]
    }
  ],
  "box_metrics": [
    {"question": 4, "top_n": 2, "bottom_n": 2},
    {"question": 13, "top_n": 2, "bottom_n": 2}
  ],
  "family_order": [
    "总体",
    "玩家经验互斥",
    "整体体验分层",
    "推荐意愿分层",
    "参与平台",
    "画像_性别",
    "玩家类型（口径A）"
  ]
}
```

## Derived-segment rules

- Run `scripts/apply_derived_segments.py` on de-identified response JSON and a stable-ID keyed labels JSON. Every existing label row needs `respondent_id`; input row order is irrelevant.
- Every configured group must be mutually exclusive within its family unless the configuration explicitly models overlapping boolean groups.
- Respondents outside all configured values receive `未回答` and are excluded from that family, but remain in Total.
- Use `item_index` for ordinary single-choice scales and `item_value` for NPS or numeric scales whose displayed option index differs from the score.
- Pass the resulting labels JSON to the dynamic analyzer. The family and category labels become column headers and every survey question is crossed by them.

## T2B/B2B rules

- Apply `scripts/add_box_metrics.py` before optional Total sorting.
- Default T2B combines the highest two distinct mapped scores; B2B combines the lowest two. Reversed option order must not change the result. Declare all scoring questions via `scales` or `rating_questions`; five options alone do not imply a scale.
- Use explicit `top_items` and `bottom_items` when structural or non-scoring options exist.
- Calculate combined numerators from original counts and use the valid scoring base, excluding null/non-scoring options. Ordinary option distributions retain those options and their answered base. Means and box cells expose their own `base_n`.
- Recalculate within-family proportion significance for the combined rows.
- Matrix score questions use a separate Mean, T2B, B2B and base for each matrix row. Negative skip codes never enter that row's denominator.
- Reapplying box metrics replaces existing derived rows; it must not duplicate them. `box_metrics_all_ratings` defaults to true for declared scales. Two-band overlap on scales with fewer than four score levels is rejected unless configured as disjoint custom bands or disabled.
- Do not apply T2B/B2B to NPS unless the user explicitly requests a nonstandard additional view; keep standard detractor/passive/promoter and NPS otherwise.

## Column order

Run `scripts/reorder_group_families.py` after analysis and before sorting. Reorder group definitions and every row's cell array together. Never reorder headers without the corresponding data cells.

`scales` maps question ID to `{ "scores": {"1":5,"2":4,"3":3,"4":2,"5":1,"6":null}, "direction":"higher" }`. Keys are option IDs, values are analytical scores; null means non-scoring. Every option must appear. Direction is `higher`, `lower` or `neutral` and controls interpretation arrows only. `rating_questions` remains a compatibility shorthand for explicitly confirmed option-code scoring over the full scale, not only 1–5.
