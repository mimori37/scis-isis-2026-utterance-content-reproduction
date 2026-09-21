# Derived evaluation data

Identifiers, conditions, generations, judges, numeric scores, and categorical labels.
No source dialogue, input context, gold utterance, generated utterance, or
judgment-item text. Run `python3 ../reproduce_paper_results.py` to turn these into the
reported tables and figures.

`condition` is `c_inner` or `c_style` throughout (`condA` and `condB` in the research
repository). The final generation is gen3 for `c_inner` and gen4 for `c_style`.
`in_main_aggregate` is `no` for u017 only, the one target excluded from the main
analysis because its gold intent cannot be judged from the context alone; every file
keeps its rows so the exclusion stays visible. In `split_metadata.tsv` the column is
blank for train-side targets, which the main analysis never scores.

## absolute_scores.tsv

One row per condition x generation x target x scorer. `scorer` is `auto` (a language
model applying `prompts/rubric_abs.md`) or `human` (one author). `content_rate` is the
share of that target's judgment items reproduced, each item scored 1 / 0.5 / 0;
`style_score` is the separate 0--2 style score. Human scoring covers gen0 and the final
generation only. Backs Table III and the trajectory in Fig. 3.

## pairwise_judgments.tsv

One row per target x condition x presentation order x judge, for the final generation
against gen0. `raw_pick` is what the judge picked between the two unlabelled candidates
A and B; `candidate_A_generation` and `candidate_B_generation` give what those slots
held in that order, and `winner` is `raw_pick` decoded through them. A pair counts as
decided only when `winner` agrees across the `normal` and `swap` rows; otherwise it is
unstable. Backs Fig. 2 and Fig. 5.

## new_rule_counts.tsv

Content-reproduction rules the generator reported at each generation, by its own
classification label. Only `new_rules` counts toward the stopping rule. Backs Fig. 3.

## character_prompt_length.tsv

Token count of each generation's character prompt, `tiktoken` encoding `o200k_base`.
A computational proxy, not a billed amount. Backs Fig. 4.

## context_sufficiency.tsv

One row per judgment item, 21 across the 12 test targets. `sufficiency_level` is 3
explicit / 2 inferable / 1 external-dependent / 0 invisible, and `deficit_category` is
filled for level-1 items only. The four score columns are that item's reproduction in
each condition at gen0 and at the final generation, recorded as the original marks
(circle 1 / triangle 0.5 / cross 0). The same author assigned both the levels and the
scores; the paper treats the resulting association as descriptive. Backs Fig. 6 and
Table V.

## split_metadata.tsv

Per-target split metadata for all 50 targets: source scene, train or test, position in
the scene, judgment-item count, and context length. The split is by source scene with
seed 42, giving train 38 and test 12.

## Known discrepancies with the camera-ready paper

Two reported values do not match a recalculation from these files. Both are recorded
here as they stand; the data and the aggregation are unchanged.
`reproduce_paper_results.py` prints the recalculated value and flags each case.

| Reported in | Camera-ready paper | Recalculated from these files |
|---|---|---|
| Fig. 5, exact agreement of the LLM majority with the human | 9/22 | 13/22 |
| Fig. 6, Spearman correlation of sufficiency with final reproduction | 0.78 | 0.756, i.e. 0.76 to two decimals |

The source of each discrepancy could not be resolved from the retained records.

Neighbouring values reproduce exactly. For Fig. 5 these are the direction agreements
and the per-judge exact agreements the running text quotes as 0.41--0.55 (GPT 9/22,
Opus 10/22, Gemini 12/22); for Fig. 6, the stratified means the figure plots
(1.00 / 0.61 / 0.14) and the item counts (1 / 11 / 9). The Fig. 6 recalculation also
matches `scripts/build_study04_summary.py`, the research-repository script that
produced the original aggregation.
