# Public-release manifest

Every file in this bundle, with its source in the research repository and the
transformation applied. The research repository is not published; this bundle is a
one-way extract.

| Public path | Source | Transformation | Copyright check | Notes |
|---|---|---|---|---|
| `CITATION.cff` | `(authored)` | authored | n/a | paper citation |
| `LICENSE` | `(authored)` | authored | n/a | MIT, scoped to this repository only |
| `NOTICE` | `(authored)` | authored | n/a | third-party names are not licensed by us |
| `README.md` | `(authored for this bundle)` | authored | no source text | scope of redistribution stated here |
| `metadata/cross_instance_exposure.tsv` | `common/source/asuka/utterance_sets.json` | derived metadata only | identifier relations only | which targets had their source utterance in another target's context |
| `metadata/split_metadata.tsv` | `common/source/asuka/utterance_sets.json` | derived metadata only | no dialogue, context, or gold text | target id, source scene id, split, turn index, item count, aggregate flag, context turn count |
| `prior_knowledge_control/README.md` | `(authored from run logs)` | aggregate results only | no source text | condition definitions and aggregate observations |
| `prior_knowledge_control/lexical_overlap_by_condition.tsv` | `experiments/study03_baseline-replay/runs/` | aggregate results only | numbers only | 3-gram overlap per target per condition |
| `prior_knowledge_control/substitution_tables.tsv` | `scripts/build_anonymization_control.py` | derived metadata only | proper nouns and short identifiers only | both substitution schemes in full |
| `public_release_manifest.md` | `(authored for this bundle)` | authored | no source text | records the public extraction and transformations |
| `withheld_materials.md` | `(authored for this bundle)` | authored | no source text | lists materials intentionally excluded from redistribution |
| `procedure/Makefile.research` | `Makefile` | copied unchanged | no source text | make targets that drive the procedure |
| `procedure/config.py` | `src/config.py` | copied unchanged | no source text | path and batch resolution |
| `procedure/replay_flow.py` | `src/replay_flow.py` | comments narrowed | identifiers kept, no source dialogue | behaviour identical; three comments narrowed to update isolation, so they do not read as preventing cross-instance exposure |
| `prompts/context_sufficiency_rubric.public.md` | `experiments/study04_context-sufficiency/labeling/00_rubric.md` | stripped copyrighted examples | calibrated anchor table omitted | four-level ladder and deficit types preserved |
| `prompts/diff_feedback.md` | `common/replay_prompts/diff_feedback.md` | copied unchanged | identifiers kept, no source dialogue | contains the stopping-rule status definitions |
| `prompts/gen_instruction.md` | `common/replay_prompts/gen_instruction.md` | stripped copyrighted example | two source lines in the input example removed | structure of the assembled paste preserved |
| `prompts/judge.md` | `common/replay_prompts/judge.md` | copied unchanged | no source dialogue | pairwise comparison prompt |
| `prompts/rubric_abs.md` | `common/replay_prompts/rubric_abs.md` | copied unchanged | no source dialogue | absolute scoring rubric |
| `prompts/rubric_keys.public.md` | `common/replay_prompts/rubric_keys.md` | stripped copyrighted examples | five quoted examples replaced with descriptions | instruction content preserved |
| `prompts/seed_analysis.md` | `common/replay_prompts/seed_analysis.md` | copied unchanged | identifiers kept, no source dialogue | exact prompt as used |
| `prompts/seed_design.md` | `common/replay_prompts/seed_design.md` | copied unchanged | identifiers kept, no source dialogue | exact prompt as used |
| `prompts/style_extract.md` | `common/replay_prompts/style_extract.md` | copied unchanged | identifiers kept, no source dialogue | speaking-style extraction |
| `scripts/build_anonymization_control.py` | `scripts/build_anonymization_control.py` | stripped copyrighted example | one quoted source utterance in the docstring removed | substitution tables and measures |
| `scripts/build_replay_summary.py` | `scripts/build_replay_summary.py` | copied unchanged | no source text | pairwise aggregation, flagged exclusion |
| `scripts/build_study03_figures.py` | `scripts/build_study03_figures.py` | copied unchanged | no source text | figure generation |
| `scripts/build_study03_human_figures.py` | `scripts/build_study03_human_figures.py` | copied unchanged | no source text | human-vs-auto figures |
| `scripts/build_study04_summary.py` | `scripts/build_study04_summary.py` | copied unchanged | no source text | sufficiency aggregation |
| `scripts/eval_human_vs_auto.py` | `scripts/eval_human_vs_auto.py` | copied unchanged | no source text | agreement computation |

## Verification performed

- Every file was matched against all 111 source utterances of eight characters or more
  from the utterance-set data. Zero files contain a source utterance.
- Work and character identifiers are present in eight files. They are kept deliberately,
  so that the reported prompts and the anonymization controls can be reproduced exactly.
- The substitution tables were inspected item by item. All 28 and 32 entries are proper
  nouns or short identifiers; the longest, at fourteen characters, is the work title.
  No entry is a dialogue fragment.
- No absolute local paths, credentials, tokens, or personal data were found.

## Note on an earlier assessment

An earlier audit listed five of these files as publishable unchanged. That assessment was
made from file names. On inspection the five contain work and character identifiers. They
are published because they contain no source dialogue, not because they contain no
identifiers.
