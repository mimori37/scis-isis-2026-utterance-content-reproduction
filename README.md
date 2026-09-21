# Evaluating and Diagnosing Character Utterance-Content Reproduction Using Source Utterances as References

Supplementary materials for the SCIS&ISIS 2026 paper (paper ID 139).

The source work is copyrighted, so no dialogue, context, gold utterance, generated
utterance, or judgment-item text is redistributed here. What is here is the procedure
as it was run, and the numeric results behind every reported table and figure.

| If you want to know | Go to |
|---|---|
| under what settings the experiment ran | [Experiment settings](#experiment-settings) |
| how utterances were generated and the prompts updated | [Generation and update procedure](#generation-and-update-procedure) |
| how the results were judged | [Evaluation protocol](#evaluation-protocol) |
| where the reported numbers come from | [Derived results and reproduction](#derived-results-and-reproduction) |
| whether the model could have recalled the source | [Prior-knowledge and cross-instance controls](#prior-knowledge-and-cross-instance-controls) |
| what was withheld or edited | [`REDISTRIBUTION.md`](REDISTRIBUTION.md) |

## Experiment settings

| Item | Setting |
|---|---|
| Execution | manual web interfaces, not an API; a fresh temporary chat for each stage, prompts pasted in and replies taken back by hand |
| Generator | GPT-5.5, reasoning high, June 2026 |
| Judges | GPT-5.5, Claude Opus 4.8, Gemini 3.1 Pro, July 2026 |
| Decoding settings | temperature, top-p, max tokens, seed: not exposed or controllable through the web interface |
| Generation count | one generated response per condition and generation (k=1) |
| Data split | by source scene, seed 42: train 38 / test 12 target utterances |
| Main analysis | n=11; u017 excluded, its gold intent not being judgeable from the context alone |
| Presentation order | each pair judged in both A/B orders |
| Aggregation | majority of the three LLM judges; the author's manual judgment is auxiliary, not gold |
| Update | train side only; test-side source utterances and evaluation results are never fed back |
| Language | all generation and evaluation were conducted in Japanese |

Because the web interface exposes no decoding settings and each response was generated
once, the results are observations of a single sample.

## Generation and update procedure

Each generation runs three stages -- analysis, design, generation -- and the feedback
step then revises the analysis and design prompts from the gap between the generated
and the source utterances. For one condition over five generations this is 38 pastes.

The prompts are the primary record of the experiment and are published as they were
written, in Japanese.

| Stage | Prompt |
|---|---|
| Analysis, generation 0 | [`prompts/seed_analysis.md`](prompts/seed_analysis.md) |
| Design, generation 0 | [`prompts/seed_design.md`](prompts/seed_design.md) |
| Generation | [`prompts/gen_instruction.md`](prompts/gen_instruction.md) |
| Feedback and update, including the stopping-rule status definitions | [`prompts/diff_feedback.md`](prompts/diff_feedback.md) |

[`procedure/replay_flow.py`](procedure/replay_flow.py) is the state machine that
assembles the text of each paste and parses each reply, and
[`procedure/Makefile.research`](procedure/Makefile.research) holds the make targets
that drove it. Both need the utterance-set data, which is withheld, so they record the
exact procedure rather than run as a pipeline.
[`procedure/config.py`](procedure/config.py) is the unmodified module those two import.
Its provider, API-key, and model settings belong to the authors' earlier API-based
studies and were not used here; `replay_flow.py` uses only its path resolution.

## Evaluation protocol

Each source utterance is decomposed into judgment items, created from the gold and the
context alone without seeing any generation, and fixed across all generations. Two
scores are taken. Absolute scoring rates each item reproduced 1 / partial 0.5 /
missing 0. Pairwise comparison, the main metric, asks which of two generations is
closer to the source; a winner counts only when both presentation orders agree, and
otherwise the pair is unstable. Ties and unstable pairs fold into no-difference before
the three judges are combined by majority.

| What | Rubric |
|---|---|
| Absolute scoring | [`prompts/rubric_abs.md`](prompts/rubric_abs.md) |
| Pairwise comparison | [`prompts/judge.md`](prompts/judge.md) |
| How judgment items are built | [`prompts/rubric_keys.public.md`](prompts/rubric_keys.public.md) |
| Scene-context sufficiency | [`prompts/context_sufficiency_rubric.public.md`](prompts/context_sufficiency_rubric.public.md) |

## Derived results and reproduction

[`derived/`](derived/) holds the per-unit results behind the reported numbers, as
identifiers, conditions, generations, judges, scores, and labels only.
[`derived/README.md`](derived/README.md) documents the columns.

```
python3 reproduce_paper_results.py      # no third-party packages
```

This recomputes and prints, from `derived/` alone:

| Reported as | Data | Also computed by |
|---|---|---|
| Table III, content-reproduction rate by generation | `absolute_scores.tsv` | [`scripts/eval_human_vs_auto.py`](scripts/eval_human_vs_auto.py) |
| Fig. 2, final vs gen0 judgment distribution | `pairwise_judgments.tsv` | [`scripts/build_replay_summary.py`](scripts/build_replay_summary.py) |
| Fig. 3, generation trajectory and new-rule count | `absolute_scores.tsv`, `new_rule_counts.tsv` | |
| Fig. 4, character-prompt length | `character_prompt_length.tsv` | |
| Fig. 5, judge-human agreement | `pairwise_judgments.tsv` | |
| Fig. 6 and Table V, scene-context sufficiency | `context_sufficiency.tsv` | [`scripts/build_study04_summary.py`](scripts/build_study04_summary.py) |

The scripts in [`scripts/`](scripts/) are the research-repository originals that
produced these results from the withheld raw files. They are kept as the record of how
the aggregation was done; they read research paths and will not run here.
`reproduce_paper_results.py` is the one entry point that does run.

Two reported values do not reproduce, and the script says so where it prints them. See
[Known discrepancies](REDISTRIBUTION.md#known-discrepancies-between-the-paper-and-these-data).

## Prior-knowledge and cross-instance controls

Two things can make a generation resemble the source without the method producing it,
and [`prior_knowledge_control/`](prior_knowledge_control/) documents the checks on both.

Cross-instance exposure is confirmed and its extent is recorded in
[`cross_instance_exposure.tsv`](prior_knowledge_control/cross_instance_exposure.tsv):
the test targets were presented in one batch, so for 4 of the 12 the target's own
source utterance appeared in a later target's input context. Removing it lowered the
highest character 3-gram overlap from 0.833 to 0.111.

Prior knowledge remains possible. Eight masking conditions were run, defined in
[`prior_knowledge_control/README.md`](prior_knowledge_control/README.md) with their
aggregate results; the overlap measurements are in
[`lexical_overlap_by_condition.tsv`](prior_knowledge_control/lexical_overlap_by_condition.tsv)
and both substitution schemes in full in
[`substitution_tables.tsv`](prior_knowledge_control/substitution_tables.tsv).
Replacing proper nouns did not remove every cue identifying the work, and in one
condition a character name absent from the whole input still appeared in 4 of 10
generations. [`scripts/build_anonymization_control.py`](scripts/build_anonymization_control.py)
is the implementation.

## Licensing

Code and author-written prompts and procedures are licensed under the terms in
[`LICENSE`](LICENSE). That license covers only this repository's own contents. It
grants no rights in any third-party work, title, character, or other intellectual
property referred to in these materials. See [`NOTICE`](NOTICE).
