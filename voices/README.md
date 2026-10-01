# Contributed character voice packs

The `person_01` and `person_02` packs contain original M4A recordings, prepared
mono WAV files, transcripts, reference clips and listening-test preferences.
Audio is stored in Git LFS; run `git lfs pull` after cloning.
The passages are described in [the recording script](../docs/VOICE_RECORDING_SCRIPT_ME.md).

## Selected anger performances

| Speaker | Reference | Higgs cue | Selected sample |
| --- | --- | --- | --- |
| person_01 | `person_01/prepared/reference_angry.wav` | `<\|emotion:anger\|>` | `auditions/2026-10-01/identity-refinement/person_01-B.wav` |
| person_02 | `person_02/prepared/reference_angry.wav` | `<\|emotion:bitterness\|>` | `auditions/2026-10-01/person-2-stronger/B.wav` |

Each reference WAV has an adjacent JSON transcript. The `preferred_anger.json`
files record the approved settings: BF16, temperature 0.60, top-p 0.95, top-k 50,
seed 42. Person 1's displayed audition label C refers to source file B.
Person 2's earlier identity baseline is also included and labelled in
`person_02/prepared/anger_baseline.json`; it is not the final anger choice.

These are reference-conditioned voice clones, not separately trained model
weights. The prepared numbered transcripts remain drafts unless explicitly
marked as confirmed. The source recordings and preparation metadata are retained
for further review.

## Runtime status

The packs are available for integration. They have not yet been assigned to
individual patient characters. The game still uses its configured shared Higgs
reference. Do not infer character assignments from the anonymous speaker IDs.

For a manual single-reference audition, point `higgs_reference` in the ignored
`services/config.local.json` at a prepared reference WAV (paths are relative to
the repository root) and restart the speech worker. Higgs reads the same-stem
JSON's `text` field. Per-speaker emotion cues and automatic character routing
still require integration; changing the reference alone does not implement them.

Other audition variants and personal runtime configuration remain untracked.
