# Evaluating and Diagnosing Character Utterance-Content Reproduction Using Source Utterances as References

Supplementary materials for the SCIS&ISIS 2026 paper (paper ID 139).

This repository documents the prompts, the interaction procedure, the evaluation rubrics,
the aggregation scripts, and derived metadata, so that the reported procedure can be
followed by others.

## Scope of redistribution

This repository preserves work and character identifiers where needed to reproduce the
reported prompts and anonymization controls. Copyrighted source dialogue, source contexts,
and gold utterance text are not redistributed. Names and identifiers appearing in the
materials are used solely to document the experimental procedure.

Some files were edited before publication, to remove quoted source dialogue while keeping
the instruction intact. **`public_release_manifest.md` records the transformation applied to
every file in this bundle, and is the authoritative record of what was edited.** Files whose
names end in `.public.md` are the most heavily edited; other files, including
`prompts/gen_instruction.md` and `scripts/build_anonymization_control.py`, also had quoted
source dialogue removed. The unedited originals are not redistributed.

## Contents

| Path | What it is |
|---|---|
| `prompts/seed_analysis.md` | analysis-stage prompt, generation 0 |
| `prompts/seed_design.md` | design-stage prompt, generation 0 |
| `prompts/gen_instruction.md` | generation-stage instruction; the input example omits the source lines |
| `prompts/diff_feedback.md` | feedback and update prompt, including the stopping-rule status definitions |
| `prompts/rubric_abs.md` | absolute scoring rubric |
| `prompts/judge.md` | pairwise comparison prompt |
| `prompts/style_extract.md` | speaking-style extraction prompt |
| `prompts/rubric_keys.public.md` | judgment-item construction rule; quoted examples replaced |
| `prompts/context_sufficiency_rubric.public.md` | scene-context-sufficiency rubric; the calibrated anchor table is omitted |
| `procedure/replay_flow.py` | the state machine that assembles each paste and ingests each reply |
| `procedure/config.py` | path and batch resolution used by the state machine |
| `procedure/Makefile.research` | the make targets used to drive the procedure |
| `scripts/` | aggregation, figure, and control scripts |
| `metadata/split_metadata.tsv` | per-target split metadata; identifiers and counts only, no text |
| `metadata/cross_instance_exposure.tsv` | which targets had their own source utterance in another target's context |
| `prior_knowledge_control/` | condition definitions and aggregate results of the prior-knowledge controls |

## Procedure in outline

Generation and judgment were run through manual web interfaces, not an API, so decoding
settings were not exposed or controllable. Each stage uses a fresh chat. For one condition
and five generations the procedure involves 38 pastes: three stages at generation 0, five
stages at each of generations 1 to 4, ten pairwise comparisons including reversed order,
and five absolute scorings.

`procedure/replay_flow.py` assembles the exact text for each paste and parses each reply.
Running it requires the utterance-set data, which is not redistributed here, so the script
is included as documentation of the exact procedure rather than as a runnable pipeline.

## What is not here

See `withheld_materials.md`.

## Licensing

Code and author-written prompts and procedures are licensed under the terms in `LICENSE`.
That license covers only this repository's own contents. It grants no rights in any
third-party work, title, character, or other intellectual property referred to in these
materials. See `NOTICE`.
