# Withheld materials

What is not in this bundle, and why. Each item exists in the research repository, which is
not published.

## Withheld because it is copyrighted source text

| Material | Research path | Reason |
|---|---|---|
| Full transcript of the work | `common/source/asuka/full_transcript.md` | verbatim transcription of the source |
| Scene-level dialogue transcript | `common/source/asuka/dialogue_scenes.md` | verbatim transcription of the source |
| Utterance sets | `common/source/asuka/utterance_sets.json` | contains every input context and gold utterance |
| Utterance-set previews | `common/source/asuka/utterance_sets_preview.md` | same content in readable form |
| Analysis source for the train side | `common/source/asuka/analysis_source_train.md` | source utterances of the train side |
| Judgment items | `experiments/study03_baseline-replay/eval/content_element_keys.tsv` | each item is a decomposition of a gold utterance and reproduces its content |
| Human evaluation worksheets | `experiments/study03_baseline-replay/eval/human/cond*/worksheet.md` | present the gold utterances and the generations side by side |
| Sufficiency labelling sheets | `experiments/study04_context-sufficiency/labeling/*` | present the input contexts in full |
| Calibrated anchors of the sufficiency rubric | `experiments/study04_context-sufficiency/labeling/00_rubric.md` | the three anchors quote source utterances |
| Raw paste texts of every stage | `experiments/study03_baseline-replay/runs/*/_paste.txt`, `runs/*/_transcripts/*` | each paste embeds the input contexts |
| Raw paste texts of the prior-knowledge controls | `experiments/study03_baseline-replay/runs/20260915-anon-control/_paste.*.txt` | same, including the masked variants |
| Model outputs | `runs/*/gen*/t04_gen_test.tsv`, `runs/*/gen*/04_gen_train.tsv` | generated utterances are close paraphrases of the source in some cases |
| Character prompts of each generation | `runs/*/gen*/03_chara_prompt.md` | derived from the train-side source utterances |

The aggregate numbers computed from the withheld model outputs are included, in
`prior_knowledge_control/lexical_overlap_by_condition.tsv`.

## Withheld because it is not part of the reported procedure

| Material | Reason |
|---|---|
| Task-management records and the working task list | internal project management, not part of the method |
| Planning and specification documents for the next study | describes work not reported in this paper |
| Earlier manuscript drafts and review logs | superseded |

## Withheld because it identifies people

| Material | Reason |
|---|---|
| Evaluator correspondence and assignment notes | the human evaluators are identified by role in the paper and are not named anywhere in this bundle |

## What a third party can and cannot do with this bundle

Documented from this bundle alone: the stage-specific instruction text, with copyrighted
examples removed as listed in the manifest; the stage order and paste structure; the
rubrics; the stopping rule; the aggregation and figure scripts; the substitution tables of
both anonymization schemes; and the split structure by source scene.

Not reproducible from this bundle alone: the utterance sets themselves. Rebuilding them
requires transcribing the source work and applying the curation rules described in the
paper. The transcription in the research repository was made manually, so an independent
transcription will not match it character for character.
