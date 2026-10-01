# Contributed character voice packs

The `person_01`, `person_02` and `person_03` packs contain original M4A recordings, prepared
mono WAV files, transcripts, reference clips and listening-test preferences.
Audio is stored in Git LFS; run `git lfs pull` after cloning.
The passages are described in [the recording script](../docs/VOICE_RECORDING_SCRIPT_ME.md).

## Selected anger performances

| Speaker | Reference | Higgs cue | Selected sample |
| --- | --- | --- | --- |
| person_01 | `person_01/prepared/reference_angry.wav` | `<\|emotion:anger\|>` | `auditions/2026-10-01/identity-refinement/person_01-B.wav` |
| person_02 | `person_02/prepared/reference_angry.wav` | `<\|emotion:bitterness\|>` | `auditions/2026-10-01/person-2-stronger/B.wav` |
| person_03 | `person_03/prepared/reference_angry.wav` | `<\|emotion:bitterness\|>` | `auditions/2026-10-01/person-3/anger-C.wav` |

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

## Person 3: initial listening comparison

Person 3 supplied 12 numbered performances, four short emotional comparisons and
an ambient recording. All 17 originals are preserved. Prepared mono WAV copies,
draft transcripts, source hashes, levels and file mappings are in
`person_03/prepared/`. The ambient recording retains its original level.
Files 02 and 11 have invalid final ALAC packets of about 0.085 seconds; their
decodable audio is retained and the errors are recorded in the inventory.

`reference_neutral`, `reference_angry`, `reference_sad` and `reference_happy`
use the short acted comparisons with boundary trimming and constant gain only.
Their transcripts include provisional recognition corrections and still need
listening review. Person 3's anger C (bitterness cue) was selected in the listening
test and saved in `person_03/prepared/preferred_anger.json`. The initial sadness
sample was rejected for voice identity; happiness C from the second happiness round is now preferred. No patient
assignment has been made.

Open `auditions/2026-10-01/person-3/index.html` to compare six Higgs BF16 samples:
neutral, anger without a tag, anger with the anger tag, anger with the bitterness
tag, sadness and happiness. They use temperature 0.60 and seed 42, with the same
generated sentence. The combined file follows that order with one-second gaps.
Exact feedback is retained in `listening_feedback.json` beside those samples.
The `refinement-1/index.html` comparison tests three sadness and three happiness
candidates, separating the effect of the reference recording from the delivery
cue. That round's happiness was rejected as insufficiently happy. The
`happiness-2/index.html` comparison uses a cheerful sentence, the longer passage
08 reference and enthusiasm/elation cues. It contains four new generated
candidates. The user selected C (longer happy performance plus enthusiasm); its
reference and settings are saved in `person_03/prepared/preferred_happiness.json`.
The user also selected sadness C (recorded sadness plus restrained delivery).
Its settings are saved in `person_03/prepared/preferred_sadness.json`: the sad
reference plus `<|prosody:expressive_low|>`, with no sadness emotion tag.
Anger, sadness and happiness preferences are saved; patient routing is still pending.

Reproduce a new preparation with `.venv/Scripts/python.exe
tools/prepare-voice-pack.py person_XX`; use `--device cpu` if CUDA libraries are
unavailable. The script refuses to overwrite existing preparation unless
`--resume` is passed, in which case it verifies completed source hashes.
After preparing WAV/JSON reference pairs, use
`.tools/alternative-tts-venv/Scripts/python.exe tools/audition-voice-pack.py
person_XX --out voices/auditions/NEW_DIRECTORY`. Existing audition outputs are
never overwritten. Neither tool changes game voice settings.
