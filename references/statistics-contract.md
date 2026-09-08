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
- NPS: detractor `-1`, passive `0`, promoter `+1`; report NPS as `100 × (promoters-detractors)/valid N` (−100 to 100 points) and do not report a mean.
- Derived label segments: classify respondents from original `item_index` or `item_value`, add the categories as a new column family, and cross every question by them. Keep unclassified/missing respondents in Total and out of that family.

## Significance

- Compare only columns within the same segment family. Never compare Total or columns across families.
- Default to two-sided `p < 0.10` unless the user specifies otherwise.
- Test proportions with original counts and valid bases, never rounded display percentages.
- Test means, average ranks, and respondent-level NPS codes with Welch independent-sample tests.
- Mark a cell high with the letters of same-family columns it significantly exceeds.
- Mark a cell low only when it is significantly lower than every other comparable same-family column.
- Warn that overlapping segment memberships violate strict independent-sample assumptions and should be interpreted as exploratory unless a paired/overlap-aware method is selected.

## Integrity and interpretation

- Compute actual within-family overlaps from respondent memberships, not from a manually supplied warning flag.
- Add a low-base advisory (default n < 30) per cell's effective base. This does not delete samples or alter test eligibility. Any extra minimum test base must be explicitly configured.
- Mark self-crosses where a source question defines the column family. Retain the user's numerical/statistical output but label the relationship as definition-based, not a new research finding.
- Store comparison target IDs and p values alongside letters. Validators recalculate test decisions from raw counts/vectors and check that every target belongs to the same family.
- Validate `value = numerator / denominator`, mean against its vector and score-weighted distribution, NPS against codes, box numerators against original option rows, and sample accounting against the fetch/cleaning receipts.
- Proportion z-tests and Welch tests preserve the accepted exploratory method. No automatic multiple-comparison correction or overlap-aware replacement is introduced.
