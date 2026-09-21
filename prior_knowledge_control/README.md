# Prior-knowledge control: conditions and aggregate results

These are the conditions and the aggregate numbers only. The paste texts, the model
outputs, and the source utterances are not included, because the paste texts and the
source utterances contain copyrighted source dialogue.

## Conditions

| Condition | Work/character identifiers | Target's own source utterance in the same input | Targets per input | Runs |
|---|---|---|---|---|
| june | kept | present | 12 | 1 |
| names_kept_answer_removed | kept | removed | 3 | 4 |
| words_masked_batched | replaced with plain Japanese words | present | 12 | 1 |
| words_masked | replaced with plain Japanese words | removed | 3 | 4 |
| symbols_masked | replaced with bracketed symbols | removed | 3 | 4 |
| nickname_ids_kept | only one character name replaced; a nickname kept in the context | removed | 1 | 5 |
| nickname_ids_masked | all identifiers replaced; a nickname kept in the context | removed | 1 | 5 |
| generic_nickname_question | no work context at all; a direct question | n/a | n/a | 5 |

The batches are formed so that no two targets from the same source scene appear in the
same input. With 8 source scenes on the test side and at most 4 targets from one scene,
four batches are the minimum.

## Files

- `cross_instance_exposure.tsv` -- which targets had their own source utterance in
  another target's input context, the test targets having been presented in one batch.
  This is the confirmed exposure, as distinct from the possible prior knowledge that
  the masking conditions below probe.
- `lexical_overlap_by_condition.tsv` -- character 3-gram overlap between the generated
  utterance and the source utterance, per target, per condition. The source utterance is
  substituted under masked conditions, so the comparison stays internally consistent.
- `substitution_tables.tsv` -- both substitution schemes, in full.

## Aggregate observations

- Lexical overlap above 0.3 occurred in 5 target-generation pairs across the June runs.
  One of them has a source utterance of four characters, where the 3-gram measure is
  unreliable. The remaining four are all targets whose source utterance was present in
  the same input.
- Retaining the identifiers and removing the target's own source utterance from the input
  lowered the highest overlap from 0.833 to 0.111.
- Under the plain-word masking, a work-specific term absent from the entire input appeared
  in one of the twelve generations. Under the bracketed-symbol masking, no such term
  appeared; the symbols are copied verbatim instead, so the absence is not evidence that
  the knowledge is absent.
- In the nickname conditions, a character name absent from the entire input appeared in
  4 of 10 generations. The two most frequent answers to the same question asked without
  any work context appeared in 0 of those 10.
