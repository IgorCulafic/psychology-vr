# v0.5.1 — merged seated animation and approved live services

This complete Windows package combines the animation branch with the current
consultation game. It includes all previous runtime files and voice packs; no
older release or patch folders are required. Initial setup still downloads the
AI models. Unity Editor and Unreal Engine are not needed to run it.

## Changes

- Ivan's recorded seated idle now drives the body while facial acting and neck
  movement are applied over it. Body/face shoulders and clothing stay aligned.
- Updated Ivan wardrobe, responsive trouser folds and shoe geometry, with visual
  pressure/deformation on the consultation chair cushions.
- Corrected overlapping material, hair/texture, prefab and Git LFS references
  when merging `feature/animation-optimization` into the current main branch.
- Preserves the four scenario voices, approved emotional synthesis settings,
  BF16 Higgs, Gemma Q4, CPU Whisper, dialogue guidance, interruption tracking,
  fullscreen/subtitle controls and automatic session/resource diagnostics.

This merge changes animation/rendering. It does not implement the handoff's
proposed Q8 residency scheduler, combined dialogue/appraisal call or a promised
15-second response deadline. The separate reported 3080 optimisations were not
available in either branch. See `BRANCH_INTEGRATION_2026_10_21.md` for the inventory,
exact source revisions, validation commands, unresolved work and rollback route.

## Verification

All 165 service regression tests pass. Unity 6000.6.0f1 successfully rebuilt the
Windows player. All four characters passed the built-player face/tear/mouth checks,
and Ivan's wardrobe shader, floor-clearance and cloth-response validation passed.
The 191.467-second recorded idle passed two loops over 23,121 rendered frames,
with zero measured pause drift, root drift and loop-seam jump.

Checks use the RTX 5090 development PC in desktop mode. They do not qualify VR
frame timing or 15-second response latency on the target RTX 4090. Other patients
retain their existing body poses. Existing regional-language and unapproved
emotion-recipe limitations from v0.5.0 remain applicable.

## Upgrade and test

Close the game and run **Stop Services.cmd**. Merge the ZIP's complete
`PsychologyVR` folder into the existing installation, replacing matching files.
Keep `.cache`, `services/config.local.json` and all `logs/`. Launch normally with
**Start Desktop.cmd** or **Start VR.cmd**.

After a university test, double-click **Export Diagnostics.cmd** and send the ZIP
from `diagnostics/` for resource/timing review. Full conversations are saved
separately in `logs/sessions/`. Diagnostics exports exclude conversation text,
recordings and credentials. No data uploads automatically.
