# Gemma Q8 package for 14th-generation i9 / 64 GB / RTX 4090

Extract the complete `PsychologyVR` folder to an SSD with at least 65 GB free.
Keep all its subfolders together. Run **Setup.cmd** once, then **Start Desktop.cmd**
or **Start VR.cmd**. Setup installs its private Python dependencies; internet is
needed for that first installation. Gemma Q8, the matching MTP draft, Higgs,
Whisper and the pinned GPU executables are already included and checksum verified.
Windows, a compatible NVIDIA driver, the Visual C++ runtime and Meta Quest Link
are system prerequisites. Set Meta Quest Link as the OpenXR runtime for VR.

The application is the complete GitHub **v0.5.0-metahuman-cast** release from
commit `e170024ab3ec8750818f547e2372207c350c8f86`, with the updated service code.
Its existing player is used without a Unity rebuild. All four MetaHumans,
assigned voice packs, emotional recipes, fullscreen controls and diagnostics
are included. Source code was downloaded separately into `.cache/upstream-latest`;
the existing 3080 installation's settings and previous source files were preserved.

The primary dialogue model is **Gemma 4 12B Instruct Q8_0** from
`ggml-org/gemma-4-12B-it-GGUF`, revision
`e3e681731089efaa3f0917336944ac64752db8ba`. The full weight file and its matching
MTP assistant are pinned by SHA-256 in `services/portable-manifest.json`.
No multimodal projector is needed for this text-dialogue application.

The default keeps **BF16 cloned voice quality**, following the earlier listening
decision. It puts **32 Gemma layers on GPU** and the remaining layers in system
RAM. This trades dialogue speed for VRAM headroom. The target is one 24 GB 4090,
64 GB system RAM and a 14th-generation i9 (corrected from the original 13900K
description; exact SKU unconfirmed). Full-pipeline latency on this exact target
has not been verified. See the [15-second Montenegrin optimization plan](LATENCY_15_SECONDS_MONTENEGRIN.md).

The inherited voices remain Ivan → Igor, Stefan → Person 1, Nikola → Person 2,
and Alex → Person 3. Original recordings, transcripts, per-emotion references,
sampling recipes and reference checksums are retained. Voice models and encoded
references remain resident. Authored openings are prepared before play. Whole
emotional beats retain their approved delivery mode; interruptions still commit
only complete, client-confirmed speech.

The integrated speed changes are:

- Compact JSON controls for dialogue, emotion, intensity, gesture, voice style
  and gaze, with animation timing computed locally.
- Separate reusable llama.cpp slots for appraisal and dialogue; each has a
  4,096-token context. Stable character instructions precede changing state.
- Flash Attention, Q8 KV caches, an eight-thread CPU pool and tunable batches.
- Bounded conversation memory, context budgeting and language/length validation.
  Retries remain validated; useful short answers are not regenerated to fill quotas.
- Resident speech engines, voice validation, fixed-opening warmup and CPU STT
  preloading. Eight STT threads and one Higgs CPU thread reduce thread contention.
- Per-stage inference timing, token counts and cache statistics, alongside the
  latest release's GPU/RAM diagnostics. Inference metrics omit dialogue text.
- Duplicate game prevention and rejection of running services with different
  model, cache, draft or voice settings.

## Optional profiles

Close the game and open **Optimization Settings.cmd**. Changes save a configuration
backup and stop only this installation's recorded services. Restart normally.

| Option | Behavior |
| --- | --- |
| BF16 quality | Default: Q8, 32 GPU layers, BF16 cloned speech, 256/128 batches |
| Faster NF4 clone | Q8 fully on GPU, NF4 cloned speech, 512/256 batches; experimental |
| INT8 clone | Q8 fully on GPU, INT8 speech; may be slower and memory must be checked |
| Smaller VR batches | 256/128 batches to reduce peak prompt-processing load |
| Larger batches | 512/256 for prompt-throughput comparison |
| MTP on/off | Matching speculative draft, two draft tokens; verify speed while rendering |

Changing speech precision does not replace the speaker reference. NF4 and INT8
are precision comparisons; their voices are **not the approved BF16 listening
result**. NF4 produced a rejected clip during preparation, so evaluate every
speaker and emotion before choosing it. MTP passed a local constrained-JSON smoke
check; a speed benefit for real VR turns has not been established.

An optional external appraisal service is supported through `appraisal_llm_url`
and `appraisal_llm_model`. It uses that server's own template/tokenizer and context
budget. This permits a separately installed small model on a second GPU, including
a Vulkan service on an RX 7600. That GPU/runtime/model combination is not bundled
or verified here; install and benchmark the helper separately. Appraisal remains
validated before dialogue and state changes.

For Quest, compare a 72 Hz headset setting, rendering resolution and the smaller
batch profile while watching frame times. A Windows per-application driver FPS
limit is a setting on the target PC and is not transferred by this ZIP.

## Measurements and the 15-second target

Verification ran on **i9-14900K, 32 GB RAM, RTX 3080 10 GB**, without a headset.
All **174 service/helper tests pass**, including compact/full JSON compatibility,
memory, state boundaries, interruption, per-speaker routing, optional precision
selection, prompt slots and hardware overrides. The pinned Q8 and MTP models
both loaded, and MTP generated schema-constrained JSON successfully.

Three identical-prompt trials on Q8 with 32 GPU layers compared the full output
format with the optimized compact/cached format. First trials were 27.016 s and
19.106 s. Subsequent trials were **22.717 / 22.921 s** and **14.420 / 14.607 s**:
about **36% less appraisal-plus-dialogue preparation** in this small screen.
The replies differed (roughly 27–30 versus 19–21 words), and speech, STT, playback
and VR were excluded. These are not controlled equal-text model benchmarks or
4090 response-time measurements.

Optional NF4 synthesis probes had inconsistent outcomes: Alex's short neutral
line took **32.358 s**, Ivan's angry line **3.047 s**, and Stefan's line failed the
audio-quality check after retry. The probe included cold per-speaker preparation
and does not establish warmed full-pipeline latency. BF16 was retained by default.

**Under 15 seconds from microphone release to audible speech has not been
verified.** First-run model/voice warmup is excluded from a warmed latency target.
Longer emotional beats, transcription, validation retries and rendering can all
increase delay. The package records this as an unverified target in its manifest.

On the 4090, run **Benchmark Responses.cmd** after setup. It prepares eight
responses, records stage timings, median and p90, and reports whether all speech
preparation samples are below 15 seconds. It does not play those clips or claim
they were heard. To include transcription, use:

```powershell
tools/benchmark-response.ps1 -Turns 8 -Audio "C:\path\short-utterance.wav"
```

The WAV must be mono PCM16, 0.2–45 seconds. Reports are under
`services/.runtime/response-benchmark/`. Run with Quest active when evaluating GPU
competition, and also measure actual release-to-audible playback in real sessions.
Use **Export Diagnostics.cmd** to collect resource and reply timings.

An optional recorded-speech patch is documented in
[Recorded speech optimization](RECORDED_SPEECH_OPTIMIZATION.md). Apply its small
update ZIP to the existing package, then run **Enable Recorded Speech.cmd**.
Exact approved lines and previously generated speech can reuse WAVs and mouth
cues. New wording still uses live synthesis; this does not verify the 15-second
target or replace the current voice references.

## Integrity and updates

The [17 October latency audit](RTX4090_LATENCY_AUDIT.md) updates the goal to <=14 seconds
and provides measured Q8/QAT comparisons, 196 passing tests, BF16-preserving optional
profiles and a small service/settings patch. The 4090 acceptance test is still pending.
New Optimization Settings choices 8-13 are explained there. General batch/MTP toggles
now preserve the selected dialogue model. Use that audit for current instructions;
the older measurements above describe the original package.

The ZIP has an embedded per-file manifest and an adjacent SHA-256 file. Model
downloads are pinned; the original release and staged assets were checked against
upstream hashes. No existing student sessions, local configuration backups or
development recordings are packaged. Reference voices and preview samples are
the approved assets supplied by the latest release.

Keep the original installation until this package passes your 4090 headset checks.
Copy only the sessions/settings you intend to keep; applying the old 3080
configuration wholesale would undo this package's target settings.
