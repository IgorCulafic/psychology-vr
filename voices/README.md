# Contributed character voice packs

Person 1's updated mono recordings with reverb removed were approved on 2026-10-04.
The canonical references, transcripts and selected generated examples are in
`person_01/prepared/`; `voice_profile.json` lists the saved emotion presets.
They retain Higgs BF16, temperature 0.60, top-p 0.95, top-k 50 and seed 42.
Frustration keeps the previous no-cue default and its accepted bitterness alternative.
These presets are assigned to Stefan's fire scenario through `cast.json`.

The `person_01`, `person_02` and `person_03` packs contain original M4A recordings, prepared
mono WAV files, transcripts, reference clips and listening-test preferences.
Audio is stored in Git LFS; run `git lfs pull` after cloning.
The passages are described in [the recording script](../docs/VOICE_RECORDING_SCRIPT_ME.md).

## Earlier anger auditions (historical)

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

## Runtime assignments

| Scenario | Character | Speaker |
| --- | --- | --- |
| Burnout / work exhaustion | Ivan | Igor |
| Witnessing a fire | Stefan | Person 1 |
| Losing a loved one | Nikola | Person 2 |
| Earthquake | Alex | Person 3 |

`cast.json` is the runtime assignment registry. `runtime/` contains compact,
self-contained voice packs with approved audio references, transcripts and
per-emotion recipes. Rebuild these with `python tools/build-voice-cast.py` after
changing approved preferences. Restart the bridge and Higgs worker to load changes.
No Unity rebuild is needed: the bridge derives voice identity from the session's
selected scenario, independently of model-generated text.

One BF16 Higgs model handles every speaker. Encoded references are cached in CPU
memory. Approved tags, temperature and pacing override generic speech directions.
Unreviewed emotions use that speaker's neutral recipe; they never change speaker.
Igor's sadness keeps separate sentences and an added 0.38-second pause, including
streamed replies. The visual emotion remains unchanged by voice fallback.

Direct auditions without a scenario retain `higgs_reference` from local config.
Portable releases built with `--include-voice-packs` include the runtime assets;
older packages without `cast.json` retain their shared voice.

Other audition variants and personal runtime configuration remain untracked.

## Approved repair selections — October 4, 2026

The remaining listening repairs were approved as good enough. Exact feedback,
the previous presets and file hashes are preserved under
`igor_2026-10-03/remaining-voice-repairs/feedback/`; `approval.json` records the
selections. Canonical `preferred_*.json` files now use:

| Speaker / delivery | Selected repair | Settings |
| --- | --- | --- |
| Person 2 anger and transition | A | Own angry reference, bitterness cue, temperature 0.45 |
| Person 3 anger and transition | B | Longer 04 angry reference, bitterness cue, temperature 0.55 |
| Igor sadness | B | Restrained delivery, separate sentences, added 0.38-second gap, temperature 0.50 |
| Igor happiness | A | Enthusiasm cue, temperature 0.45 |
| Igor disgust | B | Whole reply with audio checks and bounded recovery, no cue, temperature 0.45 |

All retain BF16 speech, top-p 0.95, top-k 50 and initial seed 42. The presets
also record retry settings and approved sample paths. Latin input (A) was
preferred in all three pronunciation comparisons. New dialogue uses `nisam`;
recorded reference transcripts remain verbatim. Person 3's longer reference
transcript remains a draft used in the approved audition; listening approval
does not certify its transcription.

Person 1's approved mono references with reverb removed and previous generation
settings remain unchanged. The runtime assignments above apply these recipes.

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
These earlier preferences are superseded where noted in the approved repair selections;
Person 3 is now assigned to Alex's earthquake scenario.

Reproduce a new preparation with `.venv/Scripts/python.exe
tools/prepare-voice-pack.py person_XX`; use `--device cpu` if CUDA libraries are
unavailable. The script refuses to overwrite existing preparation unless
`--resume` is passed, in which case it verifies completed source hashes.
After preparing WAV/JSON reference pairs, use
`.tools/alternative-tts-venv/Scripts/python.exe tools/audition-voice-pack.py
person_XX --out voices/auditions/NEW_DIRECTORY`. Existing audition outputs are
never overwritten. Neither tool changes game voice settings.
