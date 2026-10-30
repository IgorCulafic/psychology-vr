# Latency audit and 14-second test plan

**Current plan:** the user confirmed a 15-second target to first meaningful
audible speech on 29 October. See the [revised 4090 plan](LATENCY_15_SECONDS_MONTENEGRIN.md)
for the current configuration, measurement gaps and ordered experiments. This
document retains the historical 17 October measurements and 14-second target.

**17 October 2026. Functional checks pass. The 14-second target is NOT verified on an RTX 4090.**

The 4090 was unavailable during this audit. The machine actually tested was an
i9-14900K, 32 GB RAM and RTX 3080 10 GB, driver 617.14. The intended machine is a
14th-generation i9 (exact SKU unconfirmed), 64 GB RAM and RTX 4090 24 GB.
Montenegrin and the four assigned cloned voices remain requirements. The primary
package remains Gemma 4 12B Q8; QAT Q4 is an explicitly optional dialogue comparison.

## What was run

**196 automated service/helper tests passed**, including speech-cache identity,
language settings, model selection, reply budgets and interruption behavior.

### Real dialogue models, not estimated token rates

Four sequential Alex conversation turns per configuration used the same questions
and seed 42. Speech, transcription, game rendering and playback were excluded.
The first turn includes uncached prompt work; the other three form the warm median.
Models can produce different-length answers, so this is a pipeline comparison,
not a controlled model-quality study or a pure hardware speed ratio.

| Dialogue configuration on the RTX 3080 | First turn | Warm median | Trials |
|---|---:|---:|---:|
| Gemma Q8, GPU-layer setting 32 | 26.063 s | 21.495 s | 4 |
| Gemma Q8, GPU-layer setting 36 | 38.286 s | 21.413 s | 4 |
| Gemma QAT Q4, all eligible layers on GPU | 4.127 s | 3.486 s | 4 |

Q8 dialogue decoded at about 10-11 tokens/s; fully offloaded QAT Q4 commonly
decoded around 68-70 tokens/s. **3.486 seconds is dialogue preparation only.**
It is not a 4090 result and does not include the voice pipeline.

### Real BF16 cloned speech

Each voice was warmed, then measured in two baseline/optimized pairs with the
order alternated. Eight of eight paired WAV hashes matched exactly. The optional
adapter keeps the existing sampler, reference, precision, seeds and stopping rules;
it removes per-frame CPU copies and repeated position-tensor allocation.

| Voice / test emotion | Baseline median | Adapter median |
|---|---:|---:|
| Alex / anxious | 3.634 s | 3.627 s |
| Ivan / angry | 2.885 s | 2.893 s |
| Stefan / sad (pack's neutral fallback) | 3.875 s | 3.757 s |
| Nikola / sad | 4.550 s | 4.350 s |

These short clips lasted approximately 2.9-4.9 seconds. The gain is small and
varies; Ivan was slightly slower. It cannot explain or solve a 23-second wait by
itself. Four further paired checks of the final adapter with optional unused-VRAM
release also matched WAV hashes. This is sample parity, not proof for every text.
The silence/activity checks passed; a native listener must still assess diction,
identity and emotional delivery. Whole-clip versus sentence delivery can change
phrasing even when precision and voice identity inputs stay the same.

### Transcription and the complete service path

Multilingual large-v3-turbo ran on CPU in INT8. Four known Montenegrin clips were
decoded with beam sizes 5 and 1. Median times were approximately 3.07 and 2.98 s.
After punctuation/case normalization, three of four transcripts exactly matched
the intended words with either beam size. Both decoded Ivan's “traže” as “otraže”.
This does not distinguish a speech-generation error from an ASR error. Beam 1 is
an optional speed/recognition comparison, not a large demonstrated gain.

The real STT -> appraisal -> dialogue -> BF16 speech -> Rhubarb service path also
completed for all four characters. Because this 10 GB card cannot accommodate the
target's combined full-GPU workload, dialogue was deliberately placed on CPU for
this functional check. First prepared speech took 52.981-84.685 s; median 58.880 s.
Transcription took 2.95-3.18 s. During the run, Windows reported about 1,806 MiB
shared and 9,019 MiB dedicated GPU memory for the speech process. These observations
show a constrained configuration; they are not a prediction of 4090 latency.
Shared allocation alone does not prove which tensors were paged or establish causation.

The existing Windows player separately passed its actual HTTP/WAV playback,
pause/resume and interruption regression using exact approved recording fixtures
(`STREAM_CHECK_OK`, exit 0). This was a batch-mode desktop integration check, not
an AI speed test, physical speaker-output measurement or headset/frame-time test.

## Why the reported 23-30 seconds are plausible

1. **The Q8 model is only partly on GPU.** This GGUF has 48 transformer blocks.
   In bundled llama.cpp b10909, GPU-layer counts also include the output layer:
   setting 36 selects 35 blocks plus output, leaving 13 blocks on CPU. Each generated
   token still waits for those CPU blocks. A low overall CPU percentage does not
   eliminate a bottleneck in the eight inference threads or memory bandwidth.
2. **Two model requests run sequentially.** The first appraises the student's remark
   and updates the relationship; the second writes the validated reply. JSON control
   fields also consume generated tokens. At 10 tokens/s, 140 tokens alone require
   roughly 14 seconds, before prompt processing, speech recognition or synthesis.
3. **Sentence mode is not waveform streaming.** The complete first sentence WAV and
   its lip alignment must be ready before it is published. Later sentences render
   serially while the game plays earlier ones. If rendering the next sentence takes
   longer than the current clip's playback, a gap is unavoidable in this architecture.
4. **Memory must cover all workloads and their peaks.** Q8, BF16 speech, both CUDA
   contexts, KV caches, prefill/codec buffers and the game share the card. Reported
   idle VRAM of 20.8 GB does not prove paging, but does not guarantee peak headroom.
   More GPU layers or larger batches can make a tight configuration slower.
5. **Retries can multiply latency.** An over-budget or wrong-language dialogue reply
   is regenerated. Failed speech activity checks can also regenerate audio. A low
   token ceiling that truncates JSON or speech is not a valid solution.
6. **Recorded references are conditioning, not ready answers.** Exact approved
   answers and generated WAV cache hits are fast, but a new reply still needs neural
   synthesis. The small exact-line library cannot accelerate arbitrary new wording.

RAM use of 35 GB on a 64 GB PC is not, by itself, evidence of exhausted RAM. Idle
CPU/GPU utilization being low is normal for resident services waiting for requests.
The user's 4090 shared-memory use, clocks, active processes, actual token rates and
stage timings remain unknown until that machine can be measured.

## Changes made in this update

- Fixed batch, mouth-animation and MTP toggles silently forcing the selected model
  back to Q8. Unsupported MTP now fails without changing the selected configuration.
- Added the optional `latency-bf16` profile and complete matching example config:
  QAT Q4 fully offloaded, BF16 assigned voices, sentence delivery, an 18-word ordinary
  reply budget, compact directions, cached/stable prompts, Flash Attention, Q8 KV,
  and CPU Whisper beam 1. Explicit allowed requests for detail retain their larger
  disclosure budget. Replies are rewritten when necessary, never cut mid-speech.
- Added a clear per-turn word target below the ceiling to reduce unnecessary
  length rewrites. An overly strict ceiling can itself add retries; inspect metrics.
  A real eight-turn preset check respected all applicable budgets. The extra target
  removed the length rewrites observed in three ordinary turns in the first pass.
  Detail-capable open questions can also receive the larger budget; the ordinary
  ceiling does not apply to every question. Detailed replies request a short,
  meaningful first sentence before the fuller explanation.
- Added experimental `q8-gpu-bf16`: preserves Q8 plus BF16, tries complete GPU offload,
  uses one 4K context instead of two, smaller 128/64 batches, sentence delivery and
  releases unused speech allocator memory after synthesis. **Fit/speed on 24 GB are
  unverified.** Releasing allocator blocks can add allocation work to later calls.
- Added configuration-based sentence override and restoration of each voice pack's
  own mode, without editing reference recordings, recipes or manifests.
- Added optional transfer reduction in project-owned code; pinned model files stay
  unchanged. Speech-cache keys include the new generation settings and adapter code.
- Made Whisper beam size and compute type effective settings; beam 1 also uses
  best-of 1. Regional transcription remains `sr`, Latin output, no translation.
- Added audio-envelope mouth movement as an optional way to bypass Rhubarb's wait;
  it trades phoneme precision for faster readiness. Rhubarb can be restored separately.
- Added per-segment synthesis/alignment/readiness timings, inference timestamps,
  predicted later gaps, failures in benchmark reports and a configurable 14-second
  preparation target. Diagnostics export only allowlisted timings, not transcripts.
- Added `Check GPU Memory.cmd` and reproducible four-voice decoder comparison tooling.

The update changes Python services, settings and diagnostics. The shipped player
protocol is compatible; the fixture regression above exercised it. No new Unity
PCM streaming player or optimized SGLang speech server is included.

## Install and test on the 4090

1. Close the game and run **Stop Services.cmd**. Merge the new latency-update ZIP's
   `PsychologyVR` contents into the existing application folder. Keep your original
   `services/config.local.json`; the patch does not replace it. Settings changes save
   backups under `services/.runtime/config-backups`.
2. To preserve Q8 and BF16 first, try **Optimization Settings.cmd -> 13**. It is an
   experiment. Start the desktop game, inspect VRAM/shared-memory behavior during
   generation, and reject it if it fails to load, spills or causes pauses. The 4090
   has not been tested with this setting. Use option 1 to return to partial-Q8 BF16.
3. The strongest measured dialogue alternative is **PC Settings.cmd -> 6**, which
   installs/selects Gemma QAT Q4 (about 7 GB extra download if absent), followed by
   **Optimization Settings.cmd -> 8**. This restores BF16 explicitly and sets the
   Montenegrin low-latency options. QAT Q4 changes dialogue precision; compare quality.
4. Keep Rhubarb first. If alignment is material, compare option **9** (audio envelope)
   and restore phoneme alignment with **10**. Sentence override is **11**, restoration
   of the pack's mode is **12**. Options 4-7 now preserve your selected dialogue model.
5. Run **Benchmark Responses.cmd**. For recorded microphone input, use:
   `powershell -File tools/benchmark-response.ps1 -Turns 20 -Audio path\to\mono.wav`.
   This measures transcription through prepared WAV, not audible playback. Inspect
   `services/.runtime/response-benchmark/report.json`, especially segment waits,
   cache sources, retries, errors and maximum latency, not just its median.
6. In the actual game, measure at least 20 new turns across all four voices. Include
   cold/warm turns, ordinary questions, explicit detail and changing emotions. Measure
   from microphone release/end of speaking to meaningful audible speech, and measure
   later sentence gaps separately. Record whether speech was generated or cached.
   Repeat desktop and VR separately. A preparation result below 14 seconds cannot
   certify release-to-audible latency; a cache hit cannot certify new-text performance.

The acceptance goal is **<=14 seconds to meaningful speech**, correct Montenegrin,
assigned voice, no dropped words, reliable interruption and acceptable rendering.
Longer content can continue speaking beyond 14 seconds; its start and later gaps
are distinct from total generation time. Do not label a filler sound or cached
generic acknowledgement as the completed answer.

If the 4090 still misses the goal with both models fitting comfortably, measure
the slow stage before changing more settings. A different streaming speech backend
with bounded cache/concurrency, CUDA graphs and a Unity PCM receiver is a larger
next implementation, requiring platform and voice-quality validation. It has not
been installed or benchmarked here. A second GPU or separate speech host can retain
Q8 and BF16 if one card cannot fit them; it is not an automatic latency guarantee.

## Mobile notifications and remaining limits

The user confirmed an iPhone, connection through ChatGPT Codex/Remote, and iOS
notifications enabled. Setup: desktop Settings -> Connections -> Control this PC,
scan the QR code, use the same account/workspace, then enable ChatGPT notifications
in iOS Settings. Keep the host awake and online. Task completion alerts can open the
relevant task. Delivery is still checked by receiving a real alert; this audit has
not independently observed the phone receiving one. No SMS service was configured.

The repository remains private. The original upstream-owner write invitation to
IgorCulafic remains pending. Upstream's latest release is still v0.5.0-metahuman-cast;
the audit did not find a newer release to replace the downloaded base.

**Conclusion:** functional regressions checked here pass, and full GPU dialogue
offload is the clearest measured improvement. Neither these local component tests
nor the constrained 3080 pipeline prove the 4090 meets 14 seconds. The missing final
step is the real 4090 test with the intended voices, game and microphone.

## Evidence and sources

### Settings reference

| Setting | Original Q8/BF16 example | Optional low-latency profile 8 |
|---|---|---|
| Dialogue weights | Gemma Q8 | Gemma QAT Q4 |
| GPU-layer setting | 32 | 99 (all eligible layers) |
| Context / slots | 4096 per slot / 2 | 4096 per slot / 2 |
| Batch / microbatch | 256 / 128 | 256 / 128 |
| Inference CPU threads | 8 | 8 |
| Flash Attention / KV | On / Q8 | On / Q8 |
| MTP | Off | Off |
| Ordinary spoken ceiling | Relationship budget | 18; shorter target; detail exception |
| Speech weights | BF16 | BF16 |
| Speech reference routing | Assigned cast | Same assigned cast |
| Delivery mode | Voice pack recipe | Sentence override |
| Transfer-reduction adapter | Off | On; small variable gain |
| STT / device | large-v3-turbo / CPU | Same multilingual model / CPU |
| STT beam size | Default 5 | 1; recognition comparison |
| Language | cnr dialogue, sr STT, Latin | Same; no English fallback |
| Lip alignment | Rhubarb | Preserves selection; option 9 skips it |

Experimental profile 13 instead retains Q8, requests complete GPU offload, changes
batch/microbatch to 128/64 and cache slots to one, and enables unused-VRAM release.
The per-slot context remains 4096. These settings reduce buffers/cache demand but
do not prove that Q8, BF16 and the game fit within the 4090's usable memory budget.

- `docs/benchmarks/2026-10-17-latency-audit.json`: summarized local measurements.
- [Pinned llama.cpp offload allocation](https://github.com/ggml-org/llama.cpp/blob/b10909/src/llama-model.cpp):
  the output layer is included in this build's offload count.
- [Upstream release](https://github.com/IgorCulafic/psychology-vr/releases/tag/v0.5.0-metahuman-cast).
- [Official mobile setup](https://learn.chatgpt.com/docs/mobile).
- [Official Remote notifications](https://developers.openai.com/blog/mastering-codex-remote-for-engineering).
- [Earlier optimization roadmap](LATENCY_15_SECONDS_MONTENEGRIN.md) remains background;
  this audit supersedes its untested assumptions and updates the target to 14 seconds.
