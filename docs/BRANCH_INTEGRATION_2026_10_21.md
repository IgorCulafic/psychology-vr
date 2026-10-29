# Branch integration and optimisation handoff — 21 October 2026

The acceptance target is the university RTX 4090/64 GB PC. This integration was
performed on the RTX 5090 development PC. The separate RTX 3080 findings in the
supplied handoff describe a different installation and configuration.

## Source inventory and merge decisions

GitHub had two branches and no pull requests:

| Source | Revision | Decision |
| --- | --- | --- |
| `main` | `e170024ab3ec8750818f547e2372207c350c8f86` | Retain approved voices, dialogue rules, interruption tracking, diagnostics and fullscreen controls. |
| `feature/animation-optimization` | `cddeedde6f8e3f4e812ad46a11bf0bc298cb4f8c` | Integrate recorded seated motion, wardrobe, body/face alignment and cushion rendering. |

The branches diverged at `25ed714242acc2a7df8b1bdcc0cb52c61a9ac0f8`.
Replacing main with the feature tip would lose later voice and service work.
The integration therefore merges their histories and resolves overlapping
MetaHuman files using the newer animation assets while preserving main's service
and menu behavior. Both sets of Git LFS rules are retained. Existing untracked
local experiments and recordings are left intact.

The feature adds Ivan's recorded seated idle, torso/shoulder/face synchronization,
trouser deformation and new wardrobe, plus visual chair-cushion pressure. The
other patients retain their previous body posing. Facial acting, speech blending,
tears and the scenario voice assignments remain connected.

## What the supplied optimisation handoff does and does not establish

| Item | Status in this integration |
| --- | --- |
| Reported 3080 compact-response/Kokoro optimisations | Described by the handoff; their working source and evidence bundle are absent on this PC and neither remote branch contains those service changes. |
| Supplied 4090 timing analysis | Historical evidence supplied in the handoff; original raw logs and saved CSV/summary were not copied here. No independent recomputation is claimed. |
| Gemma Q4, BF16 Higgs, CPU Whisper and approved voices | Retained from main; no automatic model/voice downgrade. |
| Gemma Q8 and alternating GPU residency | Proposed and not implemented or benchmarked here. Q8 weights are absent. |
| Combined appraisal/dialogue call | Not implemented; current separate appraisal and generation remain. |
| Full prepared reply within 15 seconds | Unmet/unqualified: no matched 4090 end-to-end or headset measurements were performed in this merge. |
| Farewell/closure, ambiguity and repetitive-delivery cases T03–T05 | Remain follow-up work; those exact source transcripts were not available. Passing existing tests does not prove these cases fixed. |

The historical 4090 handoff reports 50 completed model replies with median total
preparation 24.894 seconds and speech preparation 17.364 seconds. Speech accounted
for 71.19% of summed preparation time. These are attributed handoff figures, not
new measurements. They justify testing BF16 speech first before assuming a faster
dialogue model solves the delay.

## Configuration and reproducibility

The retained model is `gemma-4-12b-it-qat-q4_0.gguf`, 6,975,879,296 bytes,
SHA-256 `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b`.
Unity Editor is `6000.6.0f1`. The current launcher requests context 4096, one slot,
99 GPU layers for Gemma, batch 256/microbatch 128, reasoning off and no speculation.
These are retained source settings, not newly measured 4090 optima. Local
configuration uses BF16 Higgs and CPU faster-whisper large-v3-turbo, Serbian
recognition with Latin-script output for Montenegrin conversation.

Local evidence is under `services/.runtime/integration-2026-10-21/`:
`source-audit.json` records asset GUID/LFS and retained-service checks;
`configuration.json` records the actual model/runtime hashes, driver and safe
configuration fields. The original pasted handoff is preserved there separately.
No credentials, participant conversations or raw face captures are published.

Commands from the project root:

```powershell
$taskTemp = Join-Path (Get-Location) 'services/.runtime/integration-temp'
New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
.tools/portable-env/Scripts/python.exe -m unittest discover -s services -p 'test_*.py'
& 'C:/Program Files/Unity/Hub/Editor/6000.6.0f1/Editor/Unity.exe' -batchmode -quit -projectPath D:/AI/Psychology_VR/unity -executeMethod PsychologyVR.Editor.ProjectSetup.BuildWindows -logFile D:/AI/Psychology_VR/services/.runtime/integration-unity-build.log
```

The first sandboxed service-test attempt failed on temporary-folder permissions.
The rerun with a workspace temporary directory passed all 165 tests. It covers
existing relationships, performance controls, voice routing, interruption,
cancellation, journaling and diagnostics; it is not a new language-quality rating.
The asset audit found zero duplicate IDs, zero unresolved MetaHuman references
after accounting for URP package assets, and zero unexpanded LFS image/model/idle
files.

The rebuilt player passed all four cast checks: 846 facial bindings and 72 tear
anchors per character, with the mouth-response check passing. Ivan's recorded
191.467-second idle passed two loops across 23,121 rendered frames. Measured pause
position/angle drift and loop seam position/angle were zero; actor-root drift was
zero. Head/shoulder seam distances stayed below 0.000001 metres. These values
describe the sampled diagnostic run, not every possible future pose.

Wardrobe validation sampled 5,745 poses. The cloth shader returned SRP batching
compatibility code 0, knee-bend response ranged 0.333–0.663 and hand contact 0–1;
paused contact drift was zero. The sampled lowest shoe point was -2.39 mm, within
the test's 3 mm floor-clearance tolerance; this does not promise zero clipping.

Results are versioned in `docs/generated/branch-integration-2026-10-21.json`.
Raw build, cast, idle and wardrobe logs/screenshots remain in the local evidence
directory above. To repeat built-player checks, run the Windows executable with
`-batchmode --desktop --metahuman-check --capture-path <absolute-output-folder>`
and then `-batchmode --desktop --seated-idle-check --capture-path <another-folder>`.
The second check runs the whole clip twice and takes about 6.5 minutes. Editor
wardrobe validation uses `-executeMethod PsychologyVR.Editor.IvanWardrobeSetup.Validate`.

## Use, target qualification and rollback

Use **Start Desktop.cmd** or **Start VR.cmd** after a full service restart.
After a university test, **Export Diagnostics.cmd** creates a local ZIP with
resource and timing data. Full conversations remain separately in `logs/sessions/`.
The current recorder does not measure headset frame time, shared-memory paging,
endpointing/STT end-to-end delay or actual audible onset. Its first-audio readiness
is a server-side preparation metric. Do not use it alone to claim the 15-second
target or continuous VR stability.

Next: reproduce closure/ambiguity cases from real logs, add finer stage timings,
freeze at least 20 representative turns and compare three warmed repetitions on
the 4090 with unchanged utterances/voice references. Measure VR/compositor frames
and a 30-minute mixed session. Evaluate BF16 conditioning/synthesis gains before
prototyping Q8 residency; preserve Q4 as the comparison baseline. Do not sum
independent percentiles or count a shortened utterance as an equivalent runtime gain.

For runtime rollback, stop the game/services and reinstall the complete
`v0.5.0-metahuman-cast` package, preserving `.cache`, local configuration and logs.
For source comparison, create a separate worktree at the main revision above;
avoid resetting a checkout that contains local work. The merge retains both
parent histories so the animation changes remain individually traceable.
