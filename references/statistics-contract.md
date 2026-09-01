# Statistical contract

## Sample and missingness

- Use only confirmed valid respondents.
- Calculate a separate effective base for every question and segment.
- For multi-select questions, treat selected as 1, answered-but-not-selected as 0, and all options missing as question-level missing.
- Preserve non-scoring options in distributions but exclude them from means and mean tests.
- Keep segment-missing respondents in Total when otherwise valid, but exclude them from that segment family.

## Metrics

- Single choice: option column percentages.
- Rating: valid-score mean plus option column percentages.
- Ordered 4/5/7-point rating and satisfaction questions may also report T2B and B2B when configured. T2B combines the highest two scoring options; B2B combines the lowest two. Use original counts and the same valid base, then rerun the within-family proportion tests for the combined rows.
- Multi-select: option selection percentages; totals may exceed 100%.
- Matrix: calculate and test each matrix row independently.
- Ranking: selection rate plus average rank among selected respondents.
- NPS: detractor `-1`, passive `0`, promoter `+1`; report NPS as `(promoters-detractors)/valid N` and do not report a mean.
- Derived label segments: classify respondents from original `item_index` or `item_value`, add the categories as a new column family, and cross every question by them. Keep unclassified/missing respondents in Total and out of that family.

## Significance

- Compare only columns within the same segment family. Never compare Total or columns across families.
- Default to two-sided `p < 0.10` unless the user specifies otherwise.
- Test proportions with original counts and valid bases, never rounded display percentages.
- Test means, average ranks, and respondent-level NPS codes with Welch independent-sample tests.
- Mark a cell high with the letters of same-family columns it significantly exceeds.
- Mark a cell low only when it is significantly lower than every other comparable same-family column.
- Warn that overlapping segment memberships violate strict independent-sample assumptions and should be interpreted as exploratory unless a paired/overlap-aware method is selected.
