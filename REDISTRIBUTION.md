# Redistribution note

What was edited before publication, what is withheld, and why. This replaces the
separate manifest and withheld-materials files of the first release.

## What is not redistributed

The study uses an existing work of fiction as its source. Its dialogue is copyrighted,
so no source dialogue, input context, gold utterance, generated utterance, or
judgment-item text appears anywhere in this repository. Concretely, these stay in the
unpublished research repository:

| Material | Why |
|---|---|
| Transcript of the work, scene-level dialogue, utterance sets and their previews | verbatim transcription of the source |
| Judgment items (`content_element_keys.tsv`) | each item decomposes a gold utterance and reproduces its content |
| Human evaluation worksheets, sufficiency labelling sheets | present the gold utterances, the generations, and the input contexts |
| Calibrated anchors of the sufficiency rubric | the three anchors quote source utterances |
| Raw paste texts and transcripts of every stage, including the prior-knowledge controls | each paste embeds the input contexts |
| Model outputs (`t04_gen_test.tsv`, `04_gen_train.tsv`) | generated utterances are close paraphrases of the source in some cases |
| Character prompts of each generation (`03_chara_prompt.md`) | derived from the train-side source utterances |
| Evaluator correspondence and assignment notes | identifies people |

The published derived tables carry identifiers, conditions, generations, judges,
numeric scores, and categorical labels only. Aggregate numbers computed from the
withheld model outputs are published in `prior_knowledge_control/`.

## Files edited before publication

Everything else is a verbatim copy of the file the study used. Prompts and rubrics are
primary records of the experiment and are published as they were written, including
their wording and their Japanese comments.

| Public path | Edit |
|---|---|
| `prompts/rubric_keys.public.md` | five quoted source examples replaced with descriptions |
| `prompts/context_sufficiency_rubric.public.md` | calibrated anchor table omitted; the four-level ladder and deficit types are intact |
| `prompts/gen_instruction.md` | the two source lines in the input example removed; the paste structure is intact |
| `scripts/build_anonymization_control.py` | one quoted source utterance removed from the docstring |
| `procedure/replay_flow.py` | three comments narrowed so they do not read as preventing cross-instance exposure; behaviour identical |
| `procedure/Makefile.research` | reduced to the study03 targets; see the header of that file |

Work and character identifiers are kept in the prompts and in the control scripts,
because the reported prompts and the anonymization controls cannot be reproduced
without them. They are not licensed to us and we grant no rights in them; see `NOTICE`.

Before release, every file was matched against all 111 source utterances of eight
characters or more in the utterance-set data; none contains a source utterance. Both
substitution tables were inspected entry by entry: all 28 and 32 entries are proper
nouns or short identifiers, the longest being the work title at fourteen characters.
No absolute local paths, credentials, tokens, or personal data are present.

## Known discrepancies between the paper and these data

Both are reported here rather than silently corrected, because the published figures
are the record of what was submitted. `reproduce_paper_results.py` prints the value the
data actually give, and flags each case.

| Where | Paper | These data |
|---|---|---|
| Fig. 6, Spearman rank correlation of sufficiency with final reproduction | 0.78 | 0.756 (n=21) |
| Fig. 5, exact agreement of the LLM majority with the human | 9/22 | 13/22 |

The Fig. 5 value is internally inconsistent in the paper as well: the distribution
drawn in Fig. 2 for the LLM majority (final 8 / tie 4 / gen0 1 / unstable 9) is
reproduced exactly by these data, and that distribution implies 13 exact matches, not
9. The paper's running text quotes the per-judge range 0.41--0.55, which reproduces
exactly (GPT 9/22, Opus 10/22, Gemini 12/22), so the text is unaffected.

For Fig. 6 we could not recover a definition of the correlation that yields 0.78 from
the label file. The stratified means the figure plots (1.00 / 0.61 / 0.14) and the
item counts (1 / 11 / 9) all reproduce exactly.

## What a third party can and cannot do with this bundle

Documented here: the stage-specific instruction text, with copyrighted examples removed
as listed above; the stage order and paste structure; the rubrics; the stopping rule;
the split structure by source scene; the substitution tables of both anonymization
schemes; and all reported results that do not require the withheld text.

Not reproducible from this bundle alone: the utterance sets themselves. Rebuilding them
requires transcribing the source work and applying the curation rules described in the
paper. The transcription in the research repository was made by hand, so an independent
transcription will not match it character for character. `procedure/` therefore records
the exact procedure; it is not a runnable pipeline.
